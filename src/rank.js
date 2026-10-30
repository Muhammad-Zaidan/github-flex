// Exponential CDF: maps an unbounded stat to 0..1 with `median` landing at 0.5.
const cdf = (x, median) => 1 - Math.pow(2, -x / median);

const RANKS = [
  { min: 92, rank: 'S+', label: 'Legendary' },
  { min: 82, rank: 'S', label: 'Elite' },
  { min: 70, rank: 'A+', label: 'Expert' },
  { min: 57, rank: 'A', label: 'Pro' },
  { min: 43, rank: 'B+', label: 'Skilled' },
  { min: 28, rank: 'B', label: 'Rising' },
  { min: 0, rank: 'C', label: 'Rookie' },
];

export function computeRank({ user, repos, contrib }) {
  const years = (Date.now() - new Date(user.createdAt)) / (365.25 * 864e5);
  const parts = [
    { w: 3, v: cdf(contrib?.lastYearTotal ?? 0, 400) },
    { w: 2.5, v: cdf(repos.stars, 60) },
    { w: 1.5, v: cdf(user.followers, 30) },
    { w: 1, v: cdf(repos.ownCount, 15) },
    { w: 1, v: cdf(contrib?.longest ?? 0, 14) },
    { w: 0.5, v: cdf(years, 4) },
  ];
  const wSum = parts.reduce((s, p) => s + p.w, 0);
  const score = Math.round((parts.reduce((s, p) => s + p.w * p.v, 0) / wSum) * 100);
  const tier = RANKS.find((r) => score >= r.min);
  return { score, ...tier, title: pickTitle({ user, repos, contrib }) };
}

function pickTitle({ user, repos, contrib }) {
  const c = contrib || {};
  const candidates = [
    { t: 'Streak Demon', s: (c.longest ?? 0) / 30 },
    { t: 'Commit Machine', s: (c.lastYearTotal ?? 0) / 1000 },
    { t: 'Star Collector', s: repos.stars / 100 },
    { t: 'Crowd Favorite', s: user.followers / 100 },
    { t: 'Repo Factory', s: repos.ownCount / 40 },
    { t: 'Polyglot', s: repos.languages.length >= 5 ? 0.6 : 0 },
    { t: 'OG Dev', s: (Date.now() - new Date(user.createdAt)) / (365.25 * 864e5) / 10 },
  ];
  const best = candidates.sort((a, b) => b.s - a.s)[0];
  return best.s >= 0.3 ? best.t : 'Builder in Progress';
}
