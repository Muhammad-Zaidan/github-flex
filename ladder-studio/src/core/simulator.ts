import type { CompareOp, LogicNode, Operand, Project } from './types';

export interface TimerState { acc: number; done: boolean; prevIn: boolean; running: boolean }
export interface CounterState { cv: number; done: boolean; prevIn: boolean }

export interface SimState {
  time: number;
  bits: Record<string, boolean>;
  words: Record<string, number>;
  timers: Record<string, TimerState>;
  counters: Record<string, CounterState>;
  /** previous value of edge contacts / edge-trigger state, keyed by element id */
  edge: Record<string, boolean>;
  /** power flow per element id for drawing: [powered on left side, powered on right side] */
  flow: Record<string, [boolean, boolean]>;
  /** power at the end of each rung's logic, keyed by rung id */
  rungPower: Record<string, boolean>;
}

export function initialState(p: Project): SimState {
  const s: SimState = { time: 0, bits: {}, words: {}, timers: {}, counters: {}, edge: {}, flow: {}, rungPower: {} };
  for (const t of p.tags) {
    if (t.kind === 'timer') s.timers[t.id] = { acc: 0, done: false, prevIn: false, running: false };
    else if (t.kind === 'counter') s.counters[t.id] = { cv: 0, done: false, prevIn: false };
    else if (t.kind === 'word') s.words[t.id] = 0;
    else s.bits[t.id] = false;
  }
  for (const r of p.rungs) for (const o of r.outputs) {
    if (o.kind === 'counter' && o.type === 'CTD') s.counters[o.tag] = { cv: o.preset, done: false, prevIn: false };
  }
  return s;
}

/** Bit value of a tag: plain bits, or the done bit of a timer/counter. */
export function readBit(s: SimState, tag: string): boolean {
  if (tag in s.timers) return s.timers[tag].done;
  if (tag in s.counters) return s.counters[tag].done;
  return !!s.bits[tag];
}

export function readWord(s: SimState, o: Operand | undefined): number {
  if (!o) return 0;
  if ('value' in o) return o.value;
  if (o.tag in s.timers) return Math.floor(s.timers[o.tag].acc / 100); // in 0.1 s units
  if (o.tag in s.counters) return s.counters[o.tag].cv;
  return s.words[o.tag] ?? 0;
}

function compare(op: CompareOp, a: number, b: number): boolean {
  switch (op) {
    case '=': return a === b;
    case '<>': return a !== b;
    case '>': return a > b;
    case '>=': return a >= b;
    case '<': return a < b;
    case '<=': return a <= b;
  }
}

function evalNode(n: LogicNode, powerIn: boolean, s: SimState, prev: SimState): boolean {
  let out: boolean;
  switch (n.kind) {
    case 'series': {
      let p = powerIn;
      for (const k of n.items) p = evalNode(k, p, s, prev);
      out = p;
      break;
    }
    case 'parallel': {
      out = false;
      for (const k of n.branches) out = evalNode(k, powerIn, s, prev) || out;
      break;
    }
    case 'contact': {
      const v = readBit(s, n.tag);
      let pass: boolean;
      if (n.type === 'NO') pass = v;
      else if (n.type === 'NC') pass = !v;
      else {
        const before = prev.edge[n.id] ?? false;
        pass = n.type === 'P' ? v && !before : !v && before;
        s.edge[n.id] = v;
      }
      out = powerIn && pass;
      break;
    }
    case 'compare':
      out = powerIn && compare(n.op, readWord(s, n.a), readWord(s, n.b));
      break;
  }
  s.flow[n.id] = [powerIn, out];
  return out;
}

const clampInt = (x: number) => Math.max(-32768, Math.min(32767, Math.trunc(x)));

/** Run one PLC scan. Inputs must already be set in `prev.bits`. Returns a new state. */
export function scan(p: Project, prev: SimState, dtMs: number): SimState {
  const s: SimState = {
    time: prev.time + dtMs,
    bits: { ...prev.bits },
    words: { ...prev.words },
    timers: Object.fromEntries(Object.entries(prev.timers).map(([k, v]) => [k, { ...v }])),
    counters: Object.fromEntries(Object.entries(prev.counters).map(([k, v]) => [k, { ...v }])),
    edge: { ...prev.edge },
    flow: {},
    rungPower: {},
  };

  // Timers advance once per scan, at the point their rung executes.
  for (const r of p.rungs) {
    const power = evalNode(r.logic, true, s, prev);
    s.rungPower[r.id] = power;
    for (const o of r.outputs) {
      s.flow[o.id] = [power, power];
      switch (o.kind) {
        case 'coil':
          if (o.mode === 'out') s.bits[o.tag] = power;
          else if (power) s.bits[o.tag] = o.mode === 'set';
          break;
        case 'timer': {
          const t = s.timers[o.tag] ?? (s.timers[o.tag] = { acc: 0, done: false, prevIn: false, running: false });
          if (o.type === 'TON') {
            if (power) { t.acc = Math.min(o.presetMs, t.acc + dtMs); t.done = t.acc >= o.presetMs; t.running = !t.done; }
            else { t.acc = 0; t.done = false; t.running = false; }
          } else if (o.type === 'TOF') {
            if (power) { t.acc = 0; t.done = true; t.running = false; }
            else if (t.done) {
              t.acc = Math.min(o.presetMs, t.acc + dtMs);
              t.running = t.acc < o.presetMs;
              if (!t.running) t.done = false;
            }
          } else {
            if (power && !t.prevIn && !t.running) { t.running = true; t.acc = 0; t.done = true; }
            if (t.running) {
              t.acc = Math.min(o.presetMs, t.acc + dtMs);
              if (t.acc >= o.presetMs) { t.running = false; t.done = false; }
            }
            if (!power && !t.running) t.acc = 0;
          }
          t.prevIn = power;
          break;
        }
        case 'counter': {
          const c = s.counters[o.tag] ?? (s.counters[o.tag] = { cv: 0, done: false, prevIn: false });
          const rst = o.reset ? readBit(s, o.reset) : false;
          if (rst) c.cv = o.type === 'CTU' ? 0 : o.preset;
          else if (power && !c.prevIn) c.cv = o.type === 'CTU' ? Math.min(c.cv + 1, 32767) : Math.max(c.cv - 1, 0);
          c.done = o.type === 'CTU' ? c.cv >= o.preset : c.cv <= 0;
          c.prevIn = power;
          break;
        }
        case 'math': {
          if (!power) break;
          const a = readWord(s, o.a);
          const b = readWord(s, o.b);
          const cur = s.words[o.out] ?? 0;
          let v = cur;
          switch (o.op) {
            case 'MOV': v = a; break;
            case 'ADD': v = a + b; break;
            case 'SUB': v = a - b; break;
            case 'MUL': v = a * b; break;
            case 'DIV': v = b === 0 ? cur : a / b; break;
            case 'INC': v = cur + 1; break;
            case 'DEC': v = cur - 1; break;
          }
          s.words[o.out] = clampInt(v);
          break;
        }
      }
    }
  }
  return s;
}

/** Convenience for tests: set inputs and run n scans of dt ms. */
export function run(p: Project, s: SimState, inputs: Record<string, boolean>, ms: number, dt = 10): SimState {
  let cur: SimState = { ...s, bits: { ...s.bits, ...inputs } };
  for (let t = 0; t < ms; t += dt) cur = scan(p, cur, dt);
  return cur;
}
