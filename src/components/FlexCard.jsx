import { forwardRef } from 'react';
import Heatmap from './Heatmap.jsx';
import { langColor } from '../langColors.js';
import { compact, yearsSince } from '../format.js';

const Stat = ({ label, value, hint }) => (
  <div className="stat">
    <div className="stat-value">{value}</div>
    <div className="stat-label">{label}</div>
    {hint && <div className="stat-hint">{hint}</div>}
  </div>
);

const FlexCard = forwardRef(function FlexCard({ data, rank, format, theme }, ref) {
  const { user, repos, contrib } = data;
  const story = format === 'story';

  return (
    <div ref={ref} className={`card card-${format} theme-${theme}`}>
      <div className="card-glow" />
      <div className="card-grain" />

      <header className="card-head">
        <img className="avatar" src={user.avatar} alt="" crossOrigin="anonymous" />
        <div className="who">
          <div className="name">{user.name}</div>
          <div className="login">@{user.login}</div>
        </div>
        <div className="rank">
          <div className="rank-letter">{rank.rank}</div>
          <div className="rank-score">{rank.score}/100</div>
        </div>
      </header>

      <div className="title-row">
        <span className="title-pill">{rank.title}</span>
        <span className="title-tier">{rank.label} tier</span>
      </div>

      {story && (
        <div className="hero">
          <div className="hero-num">{compact(contrib?.lastYearTotal ?? repos.stars)}</div>
          <div className="hero-label">
            {contrib ? 'contributions in the last year' : 'stars earned'}
          </div>
        </div>
      )}

      <div className="stats">
        {!story && <Stat label="Contribs / yr" value={compact(contrib?.lastYearTotal)} />}
        <Stat label="Stars" value={compact(repos.stars)} />
        <Stat label="Followers" value={compact(user.followers)} />
        <Stat label="Repos" value={compact(user.publicRepos)} />
        {story && <Stat label="Forks" value={compact(repos.forks)} />}
        {story && <Stat label="Longest streak" value={contrib ? `${contrib.longest}d` : '—'} />}
        {story && <Stat label="Current streak" value={contrib ? `${contrib.current}d` : '—'} />}
      </div>

      {contrib && (
        <section className="block">
          <div className="block-head">
            <span>Contributions</span>
            <span className="muted">
              {story ? `${compact(contrib.allTime)} all-time` : `${contrib.longest}d best streak`}
            </span>
          </div>
          <Heatmap days={contrib.days} weeks={53} />
        </section>
      )}

      {repos.languages.length > 0 && (
        <section className="block">
          <div className="block-head">
            <span>Top languages</span>
          </div>
          <div className="langbar">
            {repos.languages.map((l) => (
              <span key={l.name} style={{ width: `${l.pct}%`, background: langColor(l.name) }} />
            ))}
          </div>
          <div className="langs">
            {repos.languages.slice(0, story ? 5 : 4).map((l) => (
              <span key={l.name} className="lang">
                <i style={{ background: langColor(l.name) }} />
                {l.name}
                <b>{Math.round(l.pct)}%</b>
              </span>
            ))}
          </div>
        </section>
      )}

      {repos.topRepos.length > 0 && (
        <section className="block">
          <div className="block-head">
            <span>Top repos</span>
          </div>
          <div className="repos">
            {repos.topRepos.slice(0, story ? 3 : 2).map((r) => (
              <div key={r.name} className="repo">
                <div className="repo-name">{r.name}</div>
                <div className="repo-meta">
                  {r.language && (
                    <span>
                      <i style={{ background: langColor(r.language) }} />
                      {r.language}
                    </span>
                  )}
                  <span>★ {compact(r.stars)}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <footer className="card-foot">
        <span>on GitHub for {yearsSince(user.createdAt)}</span>
        <span className="brand">
          <span className="brand-mark" /> github-flex
        </span>
      </footer>
    </div>
  );
});

export default FlexCard;
