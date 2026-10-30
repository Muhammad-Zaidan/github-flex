const GH = 'https://api.github.com';
const CONTRIB = 'https://github-contributions-api.jogruber.de/v4';
const CACHE_TTL = 10 * 60 * 1000;

export class FlexError extends Error {
  constructor(message, kind) {
    super(message);
    this.kind = kind;
  }
}

async function gh(path) {
  const res = await fetch(`${GH}${path}`, {
    headers: { Accept: 'application/vnd.github+json' },
  });
  if (res.status === 404) throw new FlexError('User not found. Check the spelling?', 'notfound');
  if (res.status === 403 || res.status === 429) {
    const reset = Number(res.headers.get('x-ratelimit-reset')) * 1000;
    const mins = reset ? Math.max(1, Math.ceil((reset - Date.now()) / 60000)) : null;
    throw new FlexError(
      `GitHub rate limit hit${mins ? ` — try again in ~${mins} min` : ''}. (60 lookups/hour per IP)`,
      'ratelimit',
    );
  }
  if (!res.ok) throw new FlexError(`GitHub API error (${res.status}).`, 'api');
  return res.json();
}

async function fetchRepos(login, publicRepos) {
  const pages = Math.min(3, Math.max(1, Math.ceil(publicRepos / 100)));
  const all = await Promise.all(
    Array.from({ length: pages }, (_, i) =>
      gh(`/users/${login}/repos?per_page=100&page=${i + 1}&sort=pushed`),
    ),
  );
  return all.flat();
}

async function fetchContributions(login) {
  try {
    const res = await fetch(`${CONTRIB}/${login}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function isoDay(d) {
  return d.toISOString().slice(0, 10);
}

function summarizeContributions(raw) {
  if (!raw?.contributions?.length) return null;
  const today = isoDay(new Date());
  const days = raw.contributions
    .filter((d) => d.date <= today)
    .sort((a, b) => (a.date < b.date ? -1 : 1));

  let longest = 0;
  let run = 0;
  for (const d of days) {
    run = d.count > 0 ? run + 1 : 0;
    if (run > longest) longest = run;
  }

  // Current streak: today may still be empty without breaking the streak.
  let current = 0;
  let i = days.length - 1;
  if (i >= 0 && days[i].count === 0) i--;
  for (; i >= 0 && days[i].count > 0; i--) current++;

  const lastYear = days.slice(-371); // 53 full weeks for the heatmap
  const lastYearTotal = days.slice(-365).reduce((s, d) => s + d.count, 0);
  const allTime = Object.values(raw.total || {}).reduce((s, n) => s + n, 0);
  const best = days.reduce((m, d) => (d.count > m.count ? d : m), { count: 0, date: null });

  return { days: lastYear, lastYearTotal, allTime, longest, current, best };
}

function summarizeRepos(repos, login) {
  const own = repos.filter((r) => !r.fork);
  const stars = own.reduce((s, r) => s + r.stargazers_count, 0);
  const forks = own.reduce((s, r) => s + r.forks_count, 0);

  const langCount = {};
  for (const r of own) {
    if (!r.language) continue;
    // Weight by size (log) so one huge repo doesn't dominate, but tiny ones count less.
    langCount[r.language] = (langCount[r.language] || 0) + 1 + Math.log10(1 + r.size);
  }
  const langTotal = Object.values(langCount).reduce((s, n) => s + n, 0) || 1;
  const languages = Object.entries(langCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([name, n]) => ({ name, pct: (n / langTotal) * 100 }));

  const topRepos = [...own]
    .filter((r) => r.name.toLowerCase() !== login.toLowerCase())
    .sort((a, b) => b.stargazers_count - a.stargazers_count || b.forks_count - a.forks_count)
    .slice(0, 3)
    .map((r) => ({
      name: r.name,
      stars: r.stargazers_count,
      forks: r.forks_count,
      language: r.language,
      description: r.description,
    }));

  return { stars, forks, ownCount: own.length, languages, topRepos };
}

export async function loadFlex(username) {
  const key = `flex:${username.toLowerCase()}`;
  try {
    const cached = JSON.parse(sessionStorage.getItem(key) || 'null');
    if (cached && Date.now() - cached.at < CACHE_TTL) return cached.data;
  } catch {
    /* storage unavailable */
  }

  const user = await gh(`/users/${encodeURIComponent(username)}`);
  const [repos, contribRaw] = await Promise.all([
    fetchRepos(user.login, user.public_repos),
    fetchContributions(user.login),
  ]);

  const data = {
    user: {
      login: user.login,
      name: user.name || user.login,
      avatar: user.avatar_url,
      bio: user.bio,
      followers: user.followers,
      following: user.following,
      publicRepos: user.public_repos,
      createdAt: user.created_at,
      location: user.location,
    },
    repos: summarizeRepos(repos, user.login),
    contrib: summarizeContributions(contribRaw),
  };

  try {
    sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), data }));
  } catch {
    /* storage unavailable */
  }
  return data;
}
