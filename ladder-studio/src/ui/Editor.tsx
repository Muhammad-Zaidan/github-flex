import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import type { Lang } from '../i18n';
import { resolveAddresses } from '../core/addressing';
import { findElement, type InsertWhere } from '../core/model';
import type { BrandId, Element, Project, Tag, TagKind } from '../core/types';
import { ExportPanel } from './ExportPanel';
import { Explain } from './Explain';
import { Inspector } from './Inspector';
import { BrandSelect, IoTable } from './IoTable';
import { DND_MIME, LadderRung, rungLogicWidth, type DropPayload } from './LadderRung';
import {
  addLeaf, addOutput, addTag, deleteElement, deleteRung, duplicateRung, insertRung, moveRung, parentGroupId, patchElement, patchRung, patchTag,
  type LeafTool, type OutTool,
} from './ops';
import { SimPanel } from './SimPanel';
import { download, type useProjectHistory } from './store';
import { t, type Key } from './strings';
import { useSimulation } from './useSimulation';
import { slug } from '../core/export/common';

type Hist = ReturnType<typeof useProjectHistory>;
type Tab = 'props' | 'io' | 'explain' | 'export';
type MobileView = 'ladder' | 'io' | 'explain' | 'export';

interface Props {
  lang: Lang;
  hist: Hist;
  brand: BrandId;
  onBrand: (b: BrandId) => void;
  onHome: () => void;
  onLang: (l: Lang) => void;
}

const LEAF_TOOLS: { tool: LeafTool; key: Key; glyph: string }[] = [
  { tool: 'NO', key: 'el_NO', glyph: '┤ ├' },
  { tool: 'NC', key: 'el_NC', glyph: '┤/├' },
  { tool: 'P', key: 'el_P', glyph: '┤P├' },
  { tool: 'N', key: 'el_N', glyph: '┤N├' },
  { tool: 'compare', key: 'el_compare', glyph: '≥' },
];
const OUT_TOOLS: { tool: OutTool; key: Key; glyph: string }[] = [
  { tool: 'coil', key: 'el_coil', glyph: '( )' },
  { tool: 'set', key: 'el_set', glyph: '(S)' },
  { tool: 'reset', key: 'el_reset', glyph: '(R)' },
  { tool: 'timer', key: 'el_timer', glyph: 'TON' },
  { tool: 'counter', key: 'el_counter', glyph: 'CTU' },
  { tool: 'math', key: 'el_math', glyph: '+1' },
];

function useIsMobile() {
  const q = '(max-width: 900px)';
  const [m, setM] = useState(() => typeof window !== 'undefined' && window.matchMedia(q).matches);
  useEffect(() => {
    const mq = window.matchMedia(q);
    const f = () => setM(mq.matches);
    mq.addEventListener('change', f);
    return () => mq.removeEventListener('change', f);
  }, []);
  return m;
}

export function Editor({ lang, hist, brand, onBrand, onHome, onLang }: Props) {
  const L = (k: Key) => t(lang, k);
  const { project, update, undo, redo, canUndo, canRedo, replace } = hist;
  const [mode, setMode] = useState<'edit' | 'sim'>('edit');
  const [selected, setSelected] = useState<string | null>(null);
  const [activeRung, setActiveRung] = useState<string>(project.rungs[0]?.id);
  const [place, setPlace] = useState<'after' | 'parallel'>('after');
  const [tab, setTab] = useState<Tab>('props');
  const [mview, setMview] = useState<MobileView>('ladder');
  const [zoom, setZoom] = useState(() => (typeof window !== 'undefined' && window.innerWidth < 600 ? 0.7 : 1));
  const mobile = useIsMobile();
  const sim = useSimulation(project, mode === 'sim');
  const addr = useMemo(() => resolveAddresses(project, brand), [project, brand]);
  const tags = useMemo(() => new Map<string, Tag>(project.tags.map((x) => [x.id, x])), [project.tags]);
  const cols = useMemo(() => Math.max(1, ...project.rungs.map(rungLogicWidth)), [project.rungs]);
  const fileRef = useRef<HTMLInputElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // keep active rung valid
  useEffect(() => {
    if (!project.rungs.some((r) => r.id === activeRung)) setActiveRung(project.rungs[project.rungs.length - 1]?.id);
    if (selected && !findElement(project, selected)) setSelected(null);
  }, [project, activeRung, selected]);

  const select = useCallback((id: string | null, rungId?: string) => {
    setSelected(id);
    if (rungId) setActiveRung(rungId);
    if (id && !mobile) setTab('props');
  }, [mobile]);

  const insertLeaf = (tool: LeafTool, rungId = activeRung, target: string | null = selected, where: InsertWhere = place) => {
    let newId = '';
    update((p) => {
      const f = target ? findElement(p, target) : undefined;
      const rid = f && !f.isOutput ? f.rung.id : rungId;
      const [np, id] = addLeaf(p, tool, rid, f && !f.isOutput ? target : null, where);
      newId = id;
      return np;
    });
    setTimeout(() => select(newId), 0);
  };
  const insertOut = (tool: OutTool, rungId = activeRung) => {
    let newId = '';
    update((p) => {
      const f = selected ? findElement(p, selected) : undefined;
      const [np, id] = addOutput(p, tool, f ? f.rung.id : rungId);
      newId = id;
      return np;
    });
    setTimeout(() => select(newId), 0);
  };

  const onDrop = (rungId: string) => (pl: DropPayload, targetId: string | null, where: InsertWhere | 'output') => {
    setActiveRung(rungId);
    if (pl.kind === 'output') {
      let newId = '';
      update((p) => { const [np, id] = addOutput(p, pl.value as OutTool, rungId); newId = id; return np; });
      setTimeout(() => select(newId), 0);
    } else insertLeaf(pl.value as LeafTool, rungId, targetId, where === 'output' ? 'after' : where);
  };

  const del = useCallback(() => {
    if (!selected) return;
    update((p) => deleteElement(p, selected));
    setSelected(null);
  }, [selected, update]);

  // keyboard shortcuts
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const tgt = e.target as HTMLElement;
      const typing = /INPUT|TEXTAREA|SELECT/.test(tgt.tagName);
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !typing) { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y' && !typing) { e.preventDefault(); redo(); }
      else if ((e.key === 'Delete' || e.key === 'Backspace') && !typing && selected && mode === 'edit') { e.preventDefault(); del(); }
      else if (e.key === 'Escape') setSelected(null);
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [undo, redo, del, selected, mode]);

  const newTagFor = (k: TagKind) => {
    let id = '';
    update((p) => { const [np, tg] = addTag(p, k); id = tg.id; return np; });
    return id;
  };

  const pickRung = (id: string) => {
    setActiveRung(id);
    setMview('ladder');
    setTimeout(() => document.getElementById(`rung-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  };

  const openFile = async (f: File) => {
    try {
      const p = JSON.parse(await f.text()) as Project;
      if (p.version !== 1 || !Array.isArray(p.rungs) || !Array.isArray(p.tags)) throw new Error('bad');
      replace(p);
    } catch {
      alert(lang === 'id' ? 'File tidak bisa dibuka. Pilih file .rangkai.json yang dibuat dari aplikasi ini.' : 'That file could not be opened. Choose a .rangkai.json file saved from this app.');
    }
  };

  const inspector = (
    <Inspector
      lang={lang} project={project} addr={addr} selected={selected}
      onPatch={(id, patch: Partial<Element>) => update((p) => patchElement(p, id, patch), `el:${id}:${Object.keys(patch).join()}`)}
      onPatchTag={(id, patch) => update((p) => patchTag(p, id, patch), `tag:${id}:${Object.keys(patch).join()}`)}
      onNewTag={newTagFor}
      onInsert={(where) => insertLeaf('NO', activeRung, selected, where)}
      onDelete={del}
      onSelectParent={() => { const pid = selected && parentGroupId(project, selected); if (pid) setSelected(pid); }}
    />
  );
  const ioTable = (
    <IoTable lang={lang} project={project} brand={brand} addr={addr} onBrand={onBrand}
      onPatchTag={(id, patch) => update((p) => patchTag(p, id, patch), `tag:${id}:${Object.keys(patch).join()}`)}
      onAddTag={(k) => newTagFor(k)}
      onDeleteTag={(id) => update((p) => ({ ...p, tags: p.tags.filter((x) => x.id !== id) }))} />
  );
  const explain = <Explain lang={lang} project={project} addr={addr} onPickRung={pickRung} />;
  const exportPanel = <ExportPanel lang={lang} project={project} brand={brand} onBrand={onBrand} />;
  const simPanel = (compact: boolean) => (
    <SimPanel lang={lang} project={project} addr={addr} sim={sim.state} onInput={sim.setInput} paused={sim.paused} onPause={sim.setPaused}
      speed={sim.speed} onSpeed={sim.setSpeed} onReset={sim.reset} compact={compact} />
  );

  const dragStart = (pl: DropPayload) => (e: DragEvent) => {
    e.dataTransfer.setData(DND_MIME, JSON.stringify(pl));
    e.dataTransfer.effectAllowed = 'copy';
  };

  const palette = (
    <div className="palette" role="toolbar" aria-label={L('dragHint')}>
      <div className="pal-group">
        <span className="pal-l">{L('placeHint')}</span>
        <div className="seg sm" role="radiogroup" aria-label={L('placeHint')}>
          <button type="button" role="radio" aria-checked={place === 'after'} className={place === 'after' ? 'on' : ''} onClick={() => setPlace('after')}>{L('placeAfter')}</button>
          <button type="button" role="radio" aria-checked={place === 'parallel'} className={place === 'parallel' ? 'on' : ''} onClick={() => setPlace('parallel')}>{L('placeParallel')}</button>
        </div>
      </div>
      <div className="pal-group">
        <span className="pal-l">{L('contacts')}</span>
        <div className="pal-items">
          {LEAF_TOOLS.map((x) => (
            <button key={x.tool} type="button" className="tool" draggable onDragStart={dragStart({ kind: 'leaf', value: x.tool })} onClick={() => insertLeaf(x.tool)}>
              <span className="glyph mono" aria-hidden>{x.glyph}</span><span>{L(x.key)}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="pal-group">
        <span className="pal-l">{L('outputs')}</span>
        <div className="pal-items">
          {OUT_TOOLS.map((x) => (
            <button key={x.tool} type="button" className="tool" draggable onDragStart={dragStart({ kind: 'output', value: x.tool })} onClick={() => insertOut(x.tool)}>
              <span className="glyph mono" aria-hidden>{x.glyph}</span><span>{L(x.key)}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  const canvas = (
    <div className="canvas" ref={canvasRef} onClick={() => setSelected(null)}>
      {mode === 'sim' && <p className="sim-hint">{L('simHint')}</p>}
      {project.rungs.map((r, i) => (
        <article key={r.id} id={`rung-${r.id}`} className={`rungcard ${activeRung === r.id ? 'active' : ''} ${sim.state.rungPower[r.id] && mode === 'sim' ? 'powered' : ''}`}
          onClick={(e) => { e.stopPropagation(); setActiveRung(r.id); setSelected(null); }}>
          <header className="rung-h">
            <span className="rnum" aria-label={`${L('rung')} ${i + 1}`}>{i + 1}</span>
            {mode === 'edit'
              ? <input className="rtitle" value={r.title ?? ''} placeholder={`${L('rung')} ${i + 1}`} aria-label={L('title')}
                  onChange={(e) => update((p) => patchRung(p, r.id, { title: e.target.value }), `rt:${r.id}`)} onClick={(e) => e.stopPropagation()} />
              : <span className="rtitle ro">{r.title || `${L('rung')} ${i + 1}`}</span>}
            {mode === 'edit' && (
              <div className="rung-actions" onClick={(e) => e.stopPropagation()}>
                <button type="button" className="icon" aria-label={L('moveUp')} title={L('moveUp')} disabled={i === 0} onClick={() => update((p) => moveRung(p, r.id, -1))}>↑</button>
                <button type="button" className="icon" aria-label={L('moveDown')} title={L('moveDown')} disabled={i === project.rungs.length - 1} onClick={() => update((p) => moveRung(p, r.id, 1))}>↓</button>
                <button type="button" className="icon" aria-label={L('duplicate')} title={L('duplicate')} onClick={() => update((p) => duplicateRung(p, r.id)[0])}>⧉</button>
                <button type="button" className="icon danger" aria-label={L('deleteRung')} title={L('deleteRung')} onClick={() => update((p) => deleteRung(p, r.id))}>×</button>
              </div>
            )}
          </header>
          <div className="rung-scroll">
            <LadderRung
              rung={r} cols={cols} tags={tags} addr={addr} scale={zoom}
              sim={mode === 'sim' ? sim.state : null}
              selected={mode === 'edit' ? selected : null}
              onSelect={mode === 'edit' ? (id) => select(id, r.id) : undefined}
              onPress={mode === 'sim' ? (tag, down) => {
                const tg = tags.get(tag);
                if ((tg?.device ?? 'pushbutton') === 'pushbutton') sim.setInput(tag, down);
                else if (down) sim.setInput(tag, !sim.state.bits[tag]);
              } : undefined}
              onDrop={mode === 'edit' ? onDrop(r.id) : undefined}
              label={r.logic.items.length === 0 ? L('emptyRung') : undefined}
            />
          </div>
          {r.comment && (mode === 'sim' || activeRung !== r.id) && <p className="rcomment">{r.comment}</p>}
          {mode === 'edit' && activeRung === r.id && (
            <textarea className="rcomment-edit" rows={2} placeholder={L('comment')} aria-label={L('comment')} value={r.comment ?? ''}
              onClick={(e) => e.stopPropagation()} onChange={(e) => update((p) => patchRung(p, r.id, { comment: e.target.value }), `rc:${r.id}`)} />
          )}
        </article>
      ))}
      {mode === 'edit' && (
        <button type="button" className="addrung" onClick={(e) => { e.stopPropagation(); let nid = ''; update((p) => { const [np, id] = insertRung(p, activeRung); nid = id; return np; }); setTimeout(() => setActiveRung(nid), 0); }}>
          + {L('addRung')}
        </button>
      )}
    </div>
  );

  const topbar = (
    <header className="topbar">
      <button type="button" className="brand-btn" onClick={onHome} aria-label={L('home')}>
        <Logo /><span className="brand-name">Rangkai</span>
      </button>
      <input className="pname" value={project.name} aria-label={L('projectName')} onChange={(e) => update((p) => ({ ...p, name: e.target.value }), 'pname')} />
      <div className="seg mode" role="radiogroup" aria-label="Mode">
        <button type="button" role="radio" aria-checked={mode === 'edit'} className={mode === 'edit' ? 'on' : ''} onClick={() => setMode('edit')}>{L('edit')}</button>
        <button type="button" role="radio" aria-checked={mode === 'sim'} className={mode === 'sim' ? 'on live' : ''} onClick={() => { setMode('sim'); setSelected(null); if (tab === 'props') setTab('explain'); }}>
          <span className="dot" aria-hidden />{L('simulate')}
        </button>
      </div>
      <div className="tb-right">
        <button type="button" className="icon" onClick={undo} disabled={!canUndo} aria-label={L('undo')} title={`${L('undo')} (Ctrl+Z)`}>↶</button>
        <button type="button" className="icon" onClick={redo} disabled={!canRedo} aria-label={L('redo')} title={`${L('redo')} (Ctrl+Y)`}>↷</button>
        <span className="hide-m"><BrandSelect lang={lang} brand={brand} onBrand={onBrand} /></span>
        <details className="menu">
          <summary aria-label={L('more')}>⋯</summary>
          <div className="menu-pop">
            <button type="button" onClick={() => download(`${slug(project.name)}.rangkai.json`, JSON.stringify(project, null, 2), 'application/json')}>{L('saveFile')}</button>
            <button type="button" onClick={() => fileRef.current?.click()}>{L('openFile')}</button>
            <div className="menu-sep" />
            <button type="button" onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.15).toFixed(2)))}>{L('zoomIn')}</button>
            <button type="button" onClick={() => setZoom((z) => Math.max(0.55, +(z - 0.15).toFixed(2)))}>{L('zoomOut')}</button>
            <div className="menu-sep" />
            <button type="button" onClick={() => onLang(lang === 'id' ? 'en' : 'id')}>{lang === 'id' ? 'English' : 'Bahasa Indonesia'}</button>
            <p className="menu-note">{L('savedLocal')}</p>
          </div>
        </details>
        <input ref={fileRef} type="file" accept=".json,application/json" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) openFile(f); e.target.value = ''; }} />
      </div>
    </header>
  );

  if (mobile) {
    return (
      <div className={`app editor mobile mode-${mode}`}>
        {topbar}
        <main className="m-main">
          {mview === 'ladder' && canvas}
          {mview === 'io' && <div className="m-panel">{ioTable}</div>}
          {mview === 'explain' && <div className="m-panel">{explain}</div>}
          {mview === 'export' && <div className="m-panel">{exportPanel}</div>}
        </main>
        {mview === 'ladder' && mode === 'edit' && selected && (
          <div className="sheet" role="dialog" aria-label={L('inspector')}>
            <div className="sheet-h"><span className="grab" aria-hidden /><button type="button" className="ghost sm" onClick={() => setSelected(null)}>{L('close')}</button></div>
            {inspector}
          </div>
        )}
        {mview === 'ladder' && mode === 'edit' && !selected && <div className="m-palette">{palette}</div>}
        {mview === 'ladder' && mode === 'sim' && <div className="m-sim">{simPanel(true)}</div>}
        <nav className="bottomnav" aria-label="View">
          {(['ladder', 'io', 'explain', 'export'] as const).map((v) => (
            <button key={v} type="button" className={mview === v ? 'on' : ''} aria-current={mview === v ? 'page' : undefined} onClick={() => setMview(v)}>
              {L(v === 'ladder' ? 'ladder' : v === 'io' ? 'io' : v === 'explain' ? 'explain' : 'export')}
            </button>
          ))}
        </nav>
      </div>
    );
  }

  return (
    <div className={`app editor mode-${mode}`}>
      {topbar}
      <div className="workspace">
        {mode === 'edit' ? <aside className="left">{palette}<p className="field-h pad">{L('dragHint')}</p></aside> : <aside className="left sim-left">{simPanel(false)}</aside>}
        <main className="center">{canvas}</main>
        <aside className="right">
          <div className="tabs" role="tablist">
            {(['props', 'io', 'explain', 'export'] as const).map((x) => (
              <button key={x} role="tab" type="button" aria-selected={tab === x} className={tab === x ? 'on' : ''} onClick={() => setTab(x)}>
                {L(x === 'props' ? 'inspector' : x === 'io' ? 'io' : x === 'explain' ? 'explain' : 'export')}
              </button>
            ))}
          </div>
          <div className="tabbody" role="tabpanel">
            {tab === 'props' && (mode === 'edit' ? inspector : <p className="muted pad">{L('simHint')}</p>)}
            {tab === 'io' && ioTable}
            {tab === 'explain' && explain}
            {tab === 'export' && exportPanel}
          </div>
        </aside>
      </div>
    </div>
  );
}

export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden className="logo">
      <path d="M4 3v22M24 3v22" className="logo-rail" />
      <path d="M4 10h5M19 10h5M9 6v8M13 6v8M4 19h7M17 19h7" className="logo-w" />
      <circle cx="14" cy="19" r="3.4" className="logo-c" />
    </svg>
  );
}
