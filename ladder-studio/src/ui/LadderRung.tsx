import { useState, type DragEvent, type KeyboardEvent, type PointerEvent } from 'react';
import type { AddressMap } from '../core/addressing';
import { readBit, readWord, type SimState } from '../core/simulator';
import type { Leaf, LogicNode, Operand, OutputEl, Rung, Tag } from '../core/types';
import type { InsertWhere } from '../core/model';

export const CW = 100; // cell width
export const CH = 78; // row height
const PADL = 14;
const OUTW = 176;
const WIRE_Y = 44; // wire offset inside a row

export interface Size { w: number; h: number }
export function size(n: LogicNode): Size {
  if (n.kind === 'series') {
    const s = n.items.map(size);
    return { w: s.reduce((a, b) => a + b.w, 0), h: Math.max(1, ...s.map((x) => x.h)) };
  }
  if (n.kind === 'parallel') {
    const s = n.branches.map(size);
    return { w: Math.max(...s.map((x) => x.w)), h: s.reduce((a, b) => a + b.h, 0) };
  }
  return { w: 1, h: 1 };
}

export const rungLogicWidth = (r: Rung) => (r.logic.items.length ? size(r.logic).w : 0);

type Prim =
  | { t: 'wire'; x1: number; y1: number; x2: number; y2: number; live: boolean; key: string }
  | { t: 'leaf'; n: Leaf; col: number; row: number }
  | { t: 'group'; id: string; col: number; row: number; w: number; h: number };

function layout(root: LogicNode, cols: number, flow: SimState['flow'] | undefined): Prim[] {
  const out: Prim[] = [];
  const X = (c: number) => PADL + c * CW;
  const Y = (r: number) => r * CH + WIRE_Y;
  const live = (id: string, side: 0 | 1) => !!flow?.[id]?.[side];
  const place = (n: LogicNode, col: number, row: number, w: number) => {
    if (n.kind === 'series') {
      out.push({ t: 'group', id: n.id, col, row, w, h: size(n).h });
      let c = col;
      n.items.forEach((it, i) => {
        const sw = size(it).w;
        const allot = i === n.items.length - 1 ? w - (c - col) : sw;
        place(it, c, row, allot);
        c += allot;
      });
      if (n.items.length === 0) out.push({ t: 'wire', x1: X(col), y1: Y(row), x2: X(col + w), y2: Y(row), live: false, key: n.id + 'e' });
      return;
    }
    if (n.kind === 'parallel') {
      const sz = size(n);
      out.push({ t: 'group', id: n.id, col, row, w, h: sz.h });
      let r = row;
      const rows: number[] = [];
      for (const b of n.branches) { rows.push(r); place(b, col, r, w); r += size(b).h; }
      for (let i = 1; i < rows.length; i++) {
        out.push({ t: 'wire', x1: X(col), y1: Y(rows[i - 1]), x2: X(col), y2: Y(rows[i]), live: live(n.id, 0), key: n.id + 'l' + i });
        const below = n.branches.slice(i).some((b) => live(b.id, 1));
        out.push({ t: 'wire', x1: X(col + w), y1: Y(rows[i - 1]), x2: X(col + w), y2: Y(rows[i]), live: below, key: n.id + 'r' + i });
      }
      return;
    }
    out.push({ t: 'leaf', n, col, row });
    if (w > 1) out.push({ t: 'wire', x1: X(col + 1), y1: Y(row), x2: X(col + w), y2: Y(row), live: live(n.id, 1), key: n.id + 'x' });
  };
  if (root.kind === 'series' && root.items.length === 0) return out;
  place(root, 0, 0, cols);
  return out;
}

const trunc = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s);
const fmtSec = (ms: number) => `${(ms / 1000).toFixed(ms % 1000 === 0 ? 0 : ms % 100 === 0 ? 1 : 2)} s`;

export interface DropPayload { kind: 'leaf' | 'output'; value: string }
export const DND_MIME = 'application/x-rangkai';

interface Props {
  rung: Rung;
  cols: number;
  tags: Map<string, Tag>;
  addr: AddressMap;
  sim?: SimState | null;
  selected?: string | null;
  onSelect?: (id: string | null) => void;
  onPress?: (tagId: string, down: boolean) => void;
  onDrop?: (p: DropPayload, targetId: string | null, where: InsertWhere | 'output') => void;
  scale?: number;
  compact?: boolean;
  label?: string;
}

export function LadderRung({ rung, cols, tags, addr, sim, selected, onSelect, onPress, onDrop, scale = 1, compact, label }: Props) {
  const [hover, setHover] = useState<{ id: string | null; where: InsertWhere | 'output' } | null>(null);
  const logicW = Math.max(cols, rungLogicWidth(rung), 1);
  const lsz = rung.logic.items.length ? size(rung.logic) : { w: 0, h: 1 };
  const rows = Math.max(lsz.h, rung.outputs.length, 1);
  const outX = PADL + logicW * CW;
  const width = outX + OUTW + PADL;
  const height = rows * CH + 8;
  const power = !!sim?.rungPower[rung.id];
  const prims = layout(rung.logic, logicW, sim?.flow);
  const name = (id?: string) => (id ? tags.get(id)?.name ?? '?' : '?');
  const ad = (id?: string) => (id ? addr[id] ?? '' : '');
  const opText = (o?: Operand) => (!o ? '?' : 'value' in o ? String(o.value) : name(o.tag));
  const interactive = !!onSelect;

  const keySel = (id: string) => (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect?.(id); }
  };

  const dragOver = (id: string | null, kind: 'leaf' | 'output') => (e: DragEvent<SVGGElement>) => {
    if (!onDrop || !e.dataTransfer.types.includes(DND_MIME)) return;
    e.preventDefault();
    e.stopPropagation();
    if (kind === 'output') { setHover({ id: null, where: 'output' }); return; }
    const r = (e.currentTarget as SVGGElement).getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width;
    const fy = (e.clientY - r.top) / r.height;
    setHover({ id, where: fy > 0.72 ? 'parallel' : fx < 0.5 ? 'before' : 'after' });
  };
  const drop = (e: DragEvent) => {
    if (!onDrop) return;
    const raw = e.dataTransfer.getData(DND_MIME);
    e.preventDefault();
    e.stopPropagation();
    if (raw && hover) {
      const p = JSON.parse(raw) as DropPayload;
      onDrop(p, hover.id, p.kind === 'output' ? 'output' : hover.where === 'output' ? 'after' : hover.where);
    }
    setHover(null);
  };

  const renderLeaf = (n: Leaf, col: number, row: number) => {
    const x = PADL + col * CW;
    const y = row * CH + WIRE_Y;
    const cx = x + CW / 2;
    const [inL, outL] = sim?.flow[n.id] ?? [false, false];
    const sel = selected === n.id;
    let body;
    let closed = false;
    let pressTag: string | null = null;
    if (n.kind === 'contact') {
      const t = tags.get(n.tag);
      const v = sim ? readBit(sim, n.tag) : false;
      closed = sim ? (n.type === 'NC' ? !v : n.type === 'NO' ? v : outL) : false;
      if (t?.kind === 'input' && onPress) pressTag = n.tag;
      body = (
        <>
          <line x1={x} y1={y} x2={cx - 9} y2={y} className={inL ? 'w live' : 'w'} />
          <line x1={cx + 9} y1={y} x2={x + CW} y2={y} className={outL ? 'w live' : 'w'} />
          {closed && <rect x={cx - 9} y={y - 13} width={18} height={26} className="closed" />}
          <line x1={cx - 9} y1={y - 15} x2={cx - 9} y2={y + 15} className={`bar ${closed ? 'on' : ''}`} />
          <line x1={cx + 9} y1={y - 15} x2={cx + 9} y2={y + 15} className={`bar ${closed ? 'on' : ''}`} />
          {n.type === 'NC' && <line x1={cx - 13} y1={y + 13} x2={cx + 13} y2={y - 13} className={`bar ${closed ? 'on' : ''}`} />}
          {(n.type === 'P' || n.type === 'N') && <text x={cx} y={y + 4.5} className="edge">{n.type}</text>}
          <text x={cx} y={y - 22} className="lbl">{trunc(name(n.tag), 12)}</text>
          {!compact && <text x={cx} y={y + 30} className="addr">{ad(n.tag)}</text>}
        </>
      );
    } else {
      const res = sim ? outL : false;
      body = (
        <>
          <line x1={x} y1={y} x2={x + 8} y2={y} className={inL ? 'w live' : 'w'} />
          <line x1={x + CW - 8} y1={y} x2={x + CW} y2={y} className={outL ? 'w live' : 'w'} />
          <rect x={x + 8} y={y - 17} width={CW - 16} height={34} rx={3} className={`box ${res ? 'on' : ''}`} />
          <text x={cx} y={y - 3} className="boxt">{trunc(`${opText(n.a)} ${n.op === '<>' ? '≠' : n.op === '>=' ? '≥' : n.op === '<=' ? '≤' : n.op} ${opText(n.b)}`, 14)}</text>
          <text x={cx} y={y + 11} className="boxs">{sim ? `${readWord(sim, n.a)} ${n.op} ${readWord(sim, n.b)}` : 'CMP'}</text>
        </>
      );
    }
    return (
      <g
        key={n.id}
        className={`el ${sel ? 'sel' : ''} ${pressTag ? 'pressable' : ''}`}
        tabIndex={interactive ? 0 : undefined}
        role={interactive ? 'button' : undefined}
        aria-label={n.kind === 'contact' ? `${n.type} ${name(n.tag)} ${ad(n.tag)}` : `compare ${opText(n.a)} ${n.op} ${opText(n.b)}`}
        aria-pressed={interactive ? sel : undefined}
        onClick={(e) => { e.stopPropagation(); if (!pressTag) onSelect?.(n.id); }}
        onKeyDown={keySel(n.id)}
        onPointerDown={pressTag ? (e: PointerEvent) => { e.stopPropagation(); try { (e.target as Element).setPointerCapture?.(e.pointerId); } catch { /* synthetic pointer */ } onPress?.(pressTag!, true); } : undefined}
        onPointerUp={pressTag ? () => onPress?.(pressTag!, false) : undefined}
        onPointerCancel={pressTag ? () => onPress?.(pressTag!, false) : undefined}
        onDragOver={dragOver(n.id, 'leaf')}
        onDragLeave={() => setHover(null)}
        onDrop={drop}
      >
        <rect x={x + 2} y={row * CH + 4} width={CW - 4} height={CH - 8} rx={6} className="hit" />
        {body}
        {hover?.id === n.id && hover.where !== 'output' && <DropMark x={x} y={row * CH} where={hover.where} />}
      </g>
    );
  };

  const renderOutput = (o: OutputEl, i: number) => {
    const y = i * CH + WIRE_Y;
    const x0 = outX;
    const cx = x0 + OUTW / 2;
    const sel = selected === o.id;
    let body;
    if (o.kind === 'coil') {
      const on = sim ? readBit(sim, o.tag) : false;
      body = (
        <>
          <line x1={x0} y1={y} x2={cx - 13} y2={y} className={power ? 'w live' : 'w'} />
          <line x1={cx + 13} y1={y} x2={x0 + OUTW} y2={y} className="w" />
          {on && <circle cx={cx} cy={y} r={13} className="coilfill" />}
          <path d={`M ${cx - 7} ${y - 15} A 17 17 0 0 0 ${cx - 7} ${y + 15} M ${cx + 7} ${y - 15} A 17 17 0 0 1 ${cx + 7} ${y + 15}`} className={`coil ${on ? 'on' : ''}`} />
          {o.mode !== 'out' && <text x={cx} y={y + 4.5} className="edge">{o.mode === 'set' ? 'S' : 'R'}</text>}
          <text x={cx} y={y - 22} className="lbl">{trunc(name(o.tag), 16)}</text>
          {!compact && <text x={cx} y={y + 30} className="addr">{ad(o.tag)}</text>}
        </>
      );
    } else {
      let head = '', l2 = '', l3 = '';
      let prog: number | null = null;
      let on = false;
      if (o.kind === 'timer') {
        head = `${o.type}  ${name(o.tag)}`;
        l2 = `PT ${fmtSec(o.presetMs)}`;
        const ts = sim?.timers[o.tag];
        if (ts) { prog = o.presetMs ? ts.acc / o.presetMs : 0; l3 = `ET ${fmtSec(ts.acc)}`; on = ts.done; }
        else l3 = ad(o.tag);
      } else if (o.kind === 'counter') {
        head = `${o.type}  ${name(o.tag)}`;
        l2 = `PV ${o.preset}${o.reset ? `  R: ${name(o.reset)}` : ''}`;
        const cs = sim?.counters[o.tag];
        if (cs) { l3 = `CV ${cs.cv}`; on = cs.done; prog = o.preset ? Math.min(1, cs.cv / o.preset) : 0; }
        else l3 = ad(o.tag);
      } else {
        head = o.op === 'MOV' ? `MOV → ${name(o.out)}` : o.op === 'INC' || o.op === 'DEC' ? `${o.op} ${name(o.out)}` : `${o.op} → ${name(o.out)}`;
        l2 = o.op === 'MOV' ? `${opText(o.a)}` : o.op === 'INC' || o.op === 'DEC' ? '' : `${opText(o.a)}, ${opText(o.b)}`;
        l3 = sim ? `= ${sim.words[o.out] ?? 0}` : ad(o.out);
      }
      body = (
        <>
          <line x1={x0} y1={y} x2={x0 + 14} y2={y} className={power ? 'w live' : 'w'} />
          <line x1={x0 + OUTW - 14} y1={y} x2={x0 + OUTW} y2={y} className="w" />
          <rect x={x0 + 14} y={y - 30} width={OUTW - 28} height={58} rx={4} className={`box ${on ? 'on' : ''}`} />
          <text x={x0 + 22} y={y - 14} className="boxh">{trunc(head, 19)}</text>
          <text x={x0 + 22} y={y + 2} className="boxs l">{trunc(l2, 22)}</text>
          <text x={x0 + 22} y={y + 17} className="boxs l mono">{trunc(l3, 22)}</text>
          {prog !== null && <rect x={x0 + 15} y={y + 23} width={(OUTW - 30) * Math.max(0, Math.min(1, prog))} height={4} className="prog" />}
        </>
      );
    }
    return (
      <g
        key={o.id}
        className={`el ${sel ? 'sel' : ''}`}
        tabIndex={interactive ? 0 : undefined}
        role={interactive ? 'button' : undefined}
        aria-label={`${o.kind} ${o.kind === 'math' ? name(o.out) : name(o.tag)}`}
        aria-pressed={interactive ? sel : undefined}
        onClick={(e) => { e.stopPropagation(); onSelect?.(o.id); }}
        onKeyDown={keySel(o.id)}
        onDragOver={dragOver(null, 'output')}
        onDrop={drop}
      >
        <rect x={x0 + 4} y={i * CH + 4} width={OUTW - 8} height={CH - 8} rx={6} className="hit" />
        {body}
      </g>
    );
  };

  const wireLive = (p: Extract<Prim, { t: 'wire' }>) => p.live;
  const logicEndY = WIRE_Y;
  const lw = lsz.w;
  return (
    <svg
      className={`rung ${compact ? 'compact' : ''}`}
      width={width * scale}
      height={height * scale}
      viewBox={`0 0 ${width} ${height}`}
      aria-label={label}
      onClick={() => onSelect?.(null)}
      onDragOver={(e) => {
        if (!onDrop || !e.dataTransfer.types.includes(DND_MIME)) return;
        e.preventDefault();
        if (!hover) setHover({ id: null, where: 'after' });
      }}
      onDragLeave={(e) => { if (e.currentTarget === e.target) setHover(null); }}
      onDrop={drop}
    >
      {/* rails */}
      <line x1={PADL} y1={0} x2={PADL} y2={height} className="rail" />
      <line x1={width - PADL} y1={0} x2={width - PADL} y2={height} className="rail" />
      {prims.map((p) => (p.t === 'wire' ? <line key={p.key} x1={p.x1} y1={p.y1} x2={p.x2} y2={p.y2} className={wireLive(p) ? 'w live' : 'w'} /> : null))}
      {prims.map((p) => (p.t === 'group' && selected === p.id ? (
        <rect key={p.id} x={PADL + p.col * CW - 4} y={p.row * CH + 2} width={p.w * CW + 8} height={p.h * CH - 4} rx={8} className="groupsel" />
      ) : null))}
      {prims.map((p) => (p.t === 'leaf' ? renderLeaf(p.n, p.col, p.row) : null))}
      {/* wire from end of logic to output column */}
      <line x1={PADL + lw * CW} y1={logicEndY} x2={outX} y2={logicEndY} className={power ? 'w live' : 'w'} />
      {rung.logic.items.length === 0 && !compact && (
        <text x={PADL + 12} y={logicEndY - 14} className="hint">{label ?? ''}</text>
      )}
      {rung.outputs.length > 1 && <line x1={outX} y1={WIRE_Y} x2={outX} y2={(rung.outputs.length - 1) * CH + WIRE_Y} className={power ? 'w live' : 'w'} />}
      {rung.outputs.map(renderOutput)}
      {rung.outputs.length === 0 && (
        <g onDragOver={dragOver(null, 'output')} onDrop={drop}>
          <rect x={outX + 14} y={WIRE_Y - 22} width={OUTW - 28} height={44} rx={6} className={`slot ${hover?.where === 'output' ? 'over' : ''}`} />
          <line x1={outX} y1={WIRE_Y} x2={outX + 14} y2={WIRE_Y} className="w" />
        </g>
      )}
      {hover?.where === 'output' && rung.outputs.length > 0 && (
        <rect x={outX + 4} y={rung.outputs.length * CH - 6} width={OUTW - 8} height={6} rx={3} className="dropbar" />
      )}
      {hover && hover.id === null && hover.where !== 'output' && (
        <rect x={PADL + lw * CW + 2} y={WIRE_Y - 18} width={6} height={36} rx={3} className="dropbar" />
      )}
    </svg>
  );
}

function DropMark({ x, y, where }: { x: number; y: number; where: InsertWhere }) {
  if (where === 'parallel') return <rect x={x + 6} y={y + CH - 8} width={CW - 12} height={6} rx={3} className="dropbar" />;
  return <rect x={where === 'before' ? x - 3 : x + CW - 3} y={y + WIRE_Y - 18} width={6} height={36} rx={3} className="dropbar" />;
}
