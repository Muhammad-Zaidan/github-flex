import { useMemo, useState } from 'react';
import type { Lang } from '../i18n';
import { BRANDS, resolveAddresses } from '../core/addressing';
import { readBit } from '../core/simulator';
import type { Project, Tag } from '../core/types';
import { TEMPLATES, defaults, type Category, type Params, type Template } from '../templates';
import { Logo } from './Editor';
import { LadderRung, rungLogicWidth } from './LadderRung';
import { t, type Key } from './strings';
import { useSimulation } from './useSimulation';

interface Props {
  lang: Lang;
  onLang: (l: Lang) => void;
  hasProject: boolean;
  onContinue: () => void;
  onBlank: () => void;
  onOpen: (p: Project) => void;
}

const capture = (e: { currentTarget: Element; pointerId: number }) => { try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* synthetic pointer */ } };

export function Home({ lang, onLang, hasProject, onContinue, onBlank, onOpen }: Props) {
  const L = (k: Key) => t(lang, k);
  const [cat, setCat] = useState<Category | 'all'>('all');
  const [picked, setPicked] = useState<Template | null>(null);
  const list = TEMPLATES.filter((x) => cat === 'all' || x.category === cat);

  return (
    <div className="app home">
      <header className="topbar home-top">
        <a className="brand-btn" href="#/"><Logo /><span className="brand-name">Rangkai</span></a>
        <div className="tb-right">
          <div className="seg sm" role="radiogroup" aria-label="Language">
            <button type="button" role="radio" aria-checked={lang === 'id'} className={lang === 'id' ? 'on' : ''} onClick={() => onLang('id')}>ID</button>
            <button type="button" role="radio" aria-checked={lang === 'en'} className={lang === 'en' ? 'on' : ''} onClick={() => onLang('en')}>EN</button>
          </div>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <h1>{L('tagline')}</h1>
            <p className="lead">{L('heroBody')}</p>
            <div className="row gap wrap">
              <a className="btn primary" href="#templates">{L('openTemplates')}</a>
              <button type="button" className="btn ghost" onClick={onBlank}>{L('startBlank')}</button>
              {hasProject && <button type="button" className="btn ghost" onClick={onContinue}>{L('continueProject')}</button>}
            </div>
          </div>
          <HeroDemo lang={lang} />
        </section>

        <section className="gallery" id="templates" aria-labelledby="tpl-h">
          <div className="gallery-h">
            <div>
              <h2 id="tpl-h">{L('templates')}</h2>
              <p className="muted">{L('templatesLead')}</p>
            </div>
            <div className="chips" role="radiogroup" aria-label={L('templates')}>
              {(['all', 'motor', 'process', 'general'] as const).map((c) => (
                <button key={c} type="button" role="radio" aria-checked={cat === c} className={`chip ${cat === c ? 'on' : ''}`} onClick={() => setCat(c)}>
                  {c === 'all' ? L('all') : L(`cat_${c}` as Key)}
                </button>
              ))}
            </div>
          </div>
          <ul className="cards">
            {list.map((tp) => <TemplateCard key={tp.id} tp={tp} lang={lang} onPick={() => setPicked(tp)} />)}
          </ul>
        </section>

        <footer className="foot">
          <div>
            <h3>{L('footerSoft')}</h3>
            <ul className="softlist">
              {BRANDS.map((b) => <li key={b.id}><strong>{b.software}</strong><span>{b.cpus}</span></li>)}
            </ul>
          </div>
          <p className="safety">{L('safety')}</p>
        </footer>
      </main>

      {picked && <TemplateDialog tp={picked} lang={lang} hasProject={hasProject} onClose={() => setPicked(null)} onOpen={(p) => { setPicked(null); onOpen(p); }} />}
    </div>
  );
}

function TemplateCard({ tp, lang, onPick }: { tp: Template; lang: Lang; onPick: () => void }) {
  const p = useMemo(() => tp.build(defaults(tp), lang), [tp, lang]);
  const addr = useMemo(() => resolveAddresses(p, 'omron'), [p]);
  const tags = useMemo(() => new Map<string, Tag>(p.tags.map((x) => [x.id, x])), [p]);
  const r = p.rungs.find((x) => x.logic.items.length > 1) ?? p.rungs[0];
  const io = p.tags.filter((x) => x.kind === 'input' || x.kind === 'output').length;
  return (
    <li className="card">
      <button type="button" className="card-btn" onClick={onPick}>
        <div className="card-prev" aria-hidden>
          <LadderRung rung={r} cols={rungLogicWidth(r)} tags={tags} addr={addr} compact scale={0.52} />
        </div>
        <div className="card-body">
          <span className="card-cat">{t(lang, `cat_${tp.category}` as Key)}</span>
          <h3>{tp.title[lang]}</h3>
          <p>{tp.summary[lang]}</p>
          <span className="card-meta">{p.rungs.length} {t(lang, 'rungs')}, {io} I/O</span>
        </div>
      </button>
    </li>
  );
}

function TemplateDialog({ tp, lang, hasProject, onClose, onOpen }: { tp: Template; lang: Lang; hasProject: boolean; onClose: () => void; onOpen: (p: Project) => void }) {
  const L = (k: Key) => t(lang, k);
  const [params, setParams] = useState<Params>(() => defaults(tp));
  const p = useMemo(() => tp.build(params, lang), [tp, params, lang]);
  const addr = useMemo(() => resolveAddresses(p, 'omron'), [p]);
  const tags = useMemo(() => new Map<string, Tag>(p.tags.map((x) => [x.id, x])), [p]);
  const cols = Math.max(1, ...p.rungs.map(rungLogicWidth));
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="tpl-title" onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}>
        <header className="modal-h">
          <div>
            <span className="card-cat">{L(`cat_${tp.category}` as Key)}</span>
            <h2 id="tpl-title">{tp.title[lang]}</h2>
            <p className="muted">{tp.summary[lang]}</p>
          </div>
          <button type="button" className="icon" onClick={onClose} aria-label={L('close')} autoFocus>×</button>
        </header>
        <div className="modal-body">
          {tp.params.length > 0 && (
            <form className="params" onSubmit={(e) => { e.preventDefault(); onOpen(p); }}>
              <h3>{L('params')}</h3>
              {tp.params.map((pr) => (
                <label key={pr.key} className={`field ${pr.type === 'boolean' ? 'check' : ''}`}>
                  {pr.type === 'boolean' ? (
                    <>
                      <input type="checkbox" checked={!!params[pr.key]} onChange={(e) => setParams({ ...params, [pr.key]: e.target.checked })} />
                      <span className="field-l">{pr.label[lang]}</span>
                    </>
                  ) : (
                    <>
                      <span className="field-l">{pr.label[lang]}{pr.unit ? ` (${pr.unit === 's' ? L('seconds') : pr.unit})` : pr.key === 'gapMs' ? ' (ms)' : ''}</span>
                      <input type="number" inputMode="decimal" min={pr.min} max={pr.max} step={pr.step} value={Number(params[pr.key])}
                        onChange={(e) => {
                          const v = Number(e.target.value);
                          if (e.target.value === '' || !Number.isFinite(v)) return;
                          setParams({ ...params, [pr.key]: Math.min(pr.max ?? v, Math.max(pr.min ?? v, v)) });
                        }} />
                    </>
                  )}
                </label>
              ))}
            </form>
          )}
          <div className="modal-prev">
            {p.rungs.slice(0, 4).map((r, i) => (
              <div key={r.id} className="prev-rung">
                <span className="prev-t"><span className="rn">{i + 1}</span>{r.title}</span>
                <div className="rung-scroll"><LadderRung rung={r} cols={cols} tags={tags} addr={addr} scale={0.62} /></div>
              </div>
            ))}
            {p.rungs.length > 4 && <p className="muted">+{p.rungs.length - 4} {L('rungs')}</p>}
          </div>
        </div>
        <footer className="modal-f">
          {hasProject && <p className="field-h">{L('replaceWarn')}</p>}
          <div className="row gap">
            <button type="button" className="ghost" onClick={onClose}>{L('cancel')}</button>
            <button type="button" className="primary" onClick={() => onOpen(p)}>{L('openInEditor')}</button>
          </div>
        </footer>
      </div>
    </div>
  );
}

/** Live self-holding circuit: the clearest "aha" moment in ladder logic. */
function HeroDemo({ lang }: { lang: Lang }) {
  const p = useMemo(() => {
    const tp = TEMPLATES.find((x) => x.id === 'dol')!;
    return tp.build({ lamps: false }, lang);
  }, [lang]);
  const sim = useSimulation(p, true);
  const addr = useMemo(() => resolveAddresses(p, 'omron'), [p]);
  const tags = useMemo(() => new Map<string, Tag>(p.tags.map((x) => [x.id, x])), [p]);
  const id = (n: string) => p.tags.find((x) => x.name === n)!.id;
  const km = readBit(sim.state, id('KM1'));
  const btn = (name: string, cls: string) => (
    <button type="button" className={`pbtn ${cls} ${sim.state.bits[id(name)] ? 'down' : ''}`}
      onPointerDown={(e) => { capture(e); sim.setInput(id(name), true); }}
      onPointerUp={() => sim.setInput(id(name), false)}
      onPointerCancel={() => sim.setInput(id(name), false)}
      onKeyDown={(e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); sim.setInput(id(name), true); } }}
      onKeyUp={(e) => { if (e.key === ' ' || e.key === 'Enter') sim.setInput(id(name), false); }}>
      {name}
    </button>
  );
  return (
    <figure className="hero-demo" aria-label="Demo">
      <div className="panel">
        <div className="rung-scroll"><LadderRung rung={p.rungs[0]} cols={3} tags={tags} addr={addr} sim={sim.state} /></div>
        <div className="panel-row">
          {btn('START', 'go')}
          {btn('STOP', 'stop')}
          <span className={`pilot ${km ? 'on' : ''}`} aria-live="polite"><span className="lampdot" aria-hidden />KM1 {km ? 'ON' : 'OFF'}</span>
        </div>
      </div>
      <figcaption>{t(lang, 'heroTry')}</figcaption>
    </figure>
  );
}
