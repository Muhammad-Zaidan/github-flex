import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { toBlob } from 'html-to-image';
import FlexCard from './components/FlexCard.jsx';
import { loadFlex } from './api.js';
import { computeRank } from './rank.js';

const FORMATS = [
  { id: 'story', label: 'Story 9:16', w: 540, h: 960 },
  { id: 'post', label: 'Post 4:5', w: 540, h: 675 },
];
const THEMES = ['aurora', 'ember', 'mint', 'mono'];

function readParams() {
  const p = new URLSearchParams(location.search);
  return {
    u: p.get('u') || '',
    format: FORMATS.some((f) => f.id === p.get('f')) ? p.get('f') : 'story',
    theme: THEMES.includes(p.get('t')) ? p.get('t') : 'aurora',
  };
}

// The stage only mounts once data loads, so track the element itself (callback ref).
function useFitScale(el, width) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setScale(Math.min(1, e.contentRect.width / width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, [el, width]);
  return scale;
}

export default function App() {
  const initial = useMemo(readParams, []);
  const [input, setInput] = useState(initial.u);
  const [format, setFormat] = useState(initial.format);
  const [theme, setTheme] = useState(initial.theme);
  const [state, setState] = useState({ status: 'idle' });
  const [busy, setBusy] = useState(null);
  const [toast, setToast] = useState('');

  const cardRef = useRef(null);
  const [stageEl, setStageEl] = useState(null);
  const fmt = FORMATS.find((f) => f.id === format);
  const scale = useFitScale(stageEl, fmt.w);

  const flash = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 2200);
  };

  const run = useCallback(async (username) => {
    const u = username.trim().replace(/^@/, '').replace(/^https?:\/\/github\.com\//, '').split('/')[0];
    if (!u) return;
    setState({ status: 'loading', username: u });
    try {
      const data = await loadFlex(u);
      setState({ status: 'done', data, rank: computeRank(data) });
      setInput(data.user.login);
    } catch (err) {
      setState({ status: 'error', message: err.message || 'Something went wrong.' });
    }
  }, []);

  useEffect(() => {
    if (initial.u) run(initial.u);
  }, [initial.u, run]);

  // Keep the URL shareable: ?u=login&f=story&t=aurora
  useEffect(() => {
    if (state.status !== 'done') return;
    const p = new URLSearchParams({ u: state.data.user.login, f: format, t: theme });
    history.replaceState(null, '', `?${p}`);
  }, [state, format, theme]);

  const renderBlob = async () => {
    await document.fonts.ready;
    const opts = {
      pixelRatio: 1080 / fmt.w,
      cacheBust: true,
      width: fmt.w,
      height: fmt.h,
      // Full-bleed export: rounded corners would leave transparent pixels on socials.
      style: { borderRadius: '0' },
    };
    // First pass warms up image/font embedding (Safari quirk), second is the real one.
    await toBlob(cardRef.current, opts);
    return toBlob(cardRef.current, opts);
  };

  const fileName = () => `github-flex-${state.data.user.login}-${format}.png`;

  const download = async () => {
    setBusy('download');
    try {
      const blob = await renderBlob();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement('a'), { href: url, download: fileName() });
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      flash('Saved! Go flex it.');
    } catch {
      flash('Could not render image.');
    } finally {
      setBusy(null);
    }
  };

  const share = async () => {
    setBusy('share');
    try {
      const blob = await renderBlob();
      const file = new File([blob], fileName(), { type: 'image/png' });
      const text = `My GitHub flex: ${state.rank.rank} rank — ${state.rank.title} 💪`;
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], text, url: location.href });
      } else {
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
        flash('Image copied — paste it anywhere.');
      }
    } catch (e) {
      if (e?.name !== 'AbortError') flash('Sharing not supported here — use Download.');
    } finally {
      setBusy(null);
    }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      flash('Link copied.');
    } catch {
      flash('Could not copy link.');
    }
  };

  const tweet = () => {
    const text = `My GitHub flex: ${state.rank.rank} rank — ${state.rank.title} 💪\n`;
    window.open(
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(location.href)}`,
      '_blank',
      'noopener',
    );
  };

  const done = state.status === 'done';

  return (
    <div className="app">
      <div className="bg-orbs" aria-hidden="true">
        <span />
        <span />
      </div>

      <header className="top">
        <a className="logo" href="./">
          <span className="brand-mark" /> GitHub <b>Flex</b>
        </a>
      </header>

      <section className={`hero-search ${done ? 'compact' : ''}`}>
        {!done && (
          <>
            <h1>
              Your GitHub, <span className="grad">worth flexing.</span>
            </h1>
            <p className="sub">
              Drop a username. Get a rank, your stats and a card made for Stories, posts and
              timelines.
            </p>
          </>
        )}
        <form
          className="search"
          onSubmit={(e) => {
            e.preventDefault();
            run(input);
          }}
        >
          <span className="at">@</span>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="github username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck="false"
            autoFocus={!initial.u}
          />
          <button type="submit" disabled={state.status === 'loading'}>
            {state.status === 'loading' ? <span className="spinner" /> : 'Flex it'}
          </button>
        </form>
        {!done && state.status !== 'loading' && (
          <div className="try">
            Try:{' '}
            {['torvalds', 'gaearon', 'sindresorhus'].map((u) => (
              <button key={u} type="button" onClick={() => run(u)}>
                {u}
              </button>
            ))}
          </div>
        )}
        {state.status === 'error' && <div className="error">{state.message}</div>}
      </section>

      {state.status === 'loading' && (
        <div className="loading">
          <div className="skeleton" />
          <p>Counting your commits…</p>
        </div>
      )}

      {done && (
        <main className="result">
          <div className="controls">
            <div className="seg" role="tablist" aria-label="Format">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  className={f.id === format ? 'on' : ''}
                  onClick={() => setFormat(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <div className="swatches" aria-label="Theme">
              {THEMES.map((t) => (
                <button
                  key={t}
                  className={`swatch sw-${t} ${t === theme ? 'on' : ''}`}
                  onClick={() => setTheme(t)}
                  aria-label={t}
                  title={t}
                />
              ))}
            </div>
          </div>

          <div className="stage" ref={setStageEl}>
            <div className="stage-inner" style={{ width: fmt.w * scale, height: fmt.h * scale }}>
              <div style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
                <FlexCard ref={cardRef} data={state.data} rank={state.rank} format={format} theme={theme} />
              </div>
            </div>
          </div>

          <div className="actions">
            <button className="primary" onClick={download} disabled={!!busy}>
              {busy === 'download' ? <span className="spinner" /> : '↓'} Download PNG
            </button>
            <button onClick={share} disabled={!!busy}>
              {busy === 'share' ? <span className="spinner" /> : '↗'} Share
            </button>
            <button onClick={tweet}>𝕏 Post</button>
            <button onClick={copyLink}>🔗 Copy link</button>
          </div>

          {!state.data.contrib && (
            <p className="note">
              Contribution data is unavailable right now, so the heatmap and streaks are hidden.
            </p>
          )}
        </main>
      )}

      <footer className="site-foot">
        Uses public GitHub data only · no login, no tracking ·{' '}
        <a href="https://github.com/Muhammad-Zaidan/github-flex" target="_blank" rel="noreferrer">
          source
        </a>
      </footer>

      <div className={`toast ${toast ? 'show' : ''}`}>{toast}</div>
    </div>
  );
}
