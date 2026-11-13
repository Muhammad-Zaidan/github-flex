import { TEMPLATES, defaults, templateById } from '../templates';
import { NC, NO } from '../templates/dsl';
import { resolveAddresses } from './addressing';
import { Ctx, stackIL } from './export/common';
import { TARGETS } from './export';
import { mitsubishiIL } from './export/mitsubishi';
import { omronMnemonic } from './export/omron';
import { insertAt, leaves, removeNode, series, contact, parallel } from './model';
import { initialState, readBit, run } from './simulator';
import type { Project } from './types';

const build = (id: string, over: Record<string, number | boolean> = {}): Project => {
  const t = templateById(id)!;
  return t.build({ ...defaults(t), ...over }, 'en');
};
const tagId = (p: Project, name: string) => p.tags.find((t) => t.name === name)!.id;

describe('simulator', () => {
  it('DOL: start latches, stop releases, overload trips', () => {
    const p = build('dol');
    const [start, stop, ol, km] = ['START', 'STOP', 'OL', 'KM1'].map((n) => tagId(p, n));
    let s = initialState(p);
    s = run(p, s, { [start]: true }, 50);
    s = run(p, s, { [start]: false }, 50);
    expect(readBit(s, km)).toBe(true);
    s = run(p, s, { [stop]: true }, 20);
    expect(readBit(s, km)).toBe(false);
    s = run(p, s, { [stop]: false, [start]: true }, 20);
    s = run(p, s, { [start]: false, [ol]: true }, 20);
    expect(readBit(s, km)).toBe(false);
  });

  it('star-delta: star first, gap, then delta; never both', () => {
    const p = build('star-delta', { starTime: 2, gapMs: 100 });
    const [start, star, delta, main] = ['START', 'KM_STAR', 'KM_DELTA', 'KM_MAIN'].map((n) => tagId(p, n));
    let s = initialState(p);
    s = run(p, s, { [start]: true }, 20);
    s = run(p, s, { [start]: false }, 0);
    let sawGap = false;
    for (let t = 0; t < 3000; t += 10) {
      s = run(p, s, {}, 10);
      expect(readBit(s, star) && readBit(s, delta)).toBe(false);
      if (!readBit(s, star) && !readBit(s, delta)) sawGap = true;
    }
    expect(sawGap).toBe(true);
    expect(readBit(s, main)).toBe(true);
    expect(readBit(s, delta)).toBe(true);
  });

  it('sequential: motors start in order', () => {
    const p = build('sequential', { motors: 3, delay: 1 });
    const [start, k1, k2, k3] = ['START', 'KM1', 'KM2', 'KM3'].map((n) => tagId(p, n));
    let s = run(p, initialState(p), { [start]: true }, 20);
    s = run(p, s, { [start]: false }, 500);
    expect([readBit(s, k1), readBit(s, k2), readBit(s, k3)]).toEqual([true, false, false]);
    s = run(p, s, {}, 600);
    expect([readBit(s, k1), readBit(s, k2), readBit(s, k3)]).toEqual([true, true, false]);
    s = run(p, s, {}, 1100);
    expect(readBit(s, k3)).toBe(true);
  });

  it('counter conveyor stops after batch, reset clears', () => {
    const p = build('conveyor-count', { batch: 3 });
    const [start, sens, reset, motor, full] = ['START', 'SENSOR', 'RESET', 'MOTOR', 'H_FULL'].map((n) => tagId(p, n));
    let s = run(p, initialState(p), { [start]: true }, 20);
    s = run(p, s, { [start]: false }, 20);
    for (let i = 0; i < 3; i++) { s = run(p, s, { [sens]: true }, 20); s = run(p, s, { [sens]: false }, 20); }
    expect(readBit(s, full)).toBe(true);
    expect(readBit(s, motor)).toBe(false);
    s = run(p, s, { [reset]: true }, 20);
    expect(readBit(s, full)).toBe(false);
  });

  it('parking counter: edge-triggered INC/DEC with compare', () => {
    const p = build('parking', { cap: 2 });
    const [inS, outS, full, cnt] = ['SENS_IN', 'SENS_OUT', 'H_FULL', 'COUNT'].map((n) => tagId(p, n));
    let s = initialState(p);
    for (let i = 0; i < 3; i++) { s = run(p, s, { [inS]: true }, 30); s = run(p, s, { [inS]: false }, 30); }
    expect(s.words[cnt]).toBe(2);
    expect(readBit(s, full)).toBe(true);
    s = run(p, s, { [outS]: true }, 30);
    expect(s.words[cnt]).toBe(1);
  });

  it('stair light toggles once per press', () => {
    const p = build('stair-light');
    const [pb, lamp] = ['PB_DOWN', 'LAMP'].map((n) => tagId(p, n));
    let s = run(p, initialState(p), { [pb]: true }, 200);
    expect(readBit(s, lamp)).toBe(true);
    s = run(p, s, { [pb]: false }, 50);
    s = run(p, s, { [pb]: true }, 200);
    expect(readBit(s, lamp)).toBe(false);
  });

  it('traffic light cycles and repeats', () => {
    const p = build('traffic', { green: 1, yellow: 0.5 });
    const [on, ga, ya, gb] = ['RUN', 'A_GREEN', 'A_YELLOW', 'B_GREEN'].map((n) => tagId(p, n));
    let s = run(p, initialState(p), { [on]: true }, 500);
    expect(readBit(s, ga)).toBe(true);
    s = run(p, s, {}, 700);
    expect(readBit(s, ya)).toBe(true);
    s = run(p, s, {}, 600);
    expect(readBit(s, gb)).toBe(true);
    s = run(p, s, {}, 1600);
    expect(readBit(s, ga)).toBe(true);
  });

  it('every template builds and runs without throwing', () => {
    for (const t of TEMPLATES) {
      const p = t.build(defaults(t), 'id');
      expect(p.rungs.length).toBeGreaterThan(0);
      run(p, initialState(p), {}, 100);
    }
  });
});

describe('model edits', () => {
  it('insert after / parallel / remove keep tree normalised', () => {
    const a = contact('a'), b = contact('b'), c = contact('c');
    let r = series(a);
    r = insertAt(r, a.id, b, 'after');
    expect(leaves(r).map((x) => (x as { tag: string }).tag)).toEqual(['a', 'b']);
    r = insertAt(r, b.id, c, 'parallel');
    expect(r.items[1].kind).toBe('parallel');
    r = removeNode(r, c.id);
    expect(r.items.map((x) => x.kind)).toEqual(['contact', 'contact']);
    r = removeNode(r, a.id);
    expect(r.items.length).toBe(1);
  });
});

describe('exporters', () => {
  it('stack IL for (A OR B) AND NOT C AND (D OR (E AND F))', () => {
    const tree = series(parallel(contact('A'), contact('B')), NC('C'), parallel(NO('D'), series(NO('E'), NO('F'))));
    const il = stackIL(tree, (pos, el) => `${pos} ${el.kind === 'contact' ? (el.type === 'NC' ? 'NOT ' : '') + el.tag : ''}`, 'ANB', 'ORB');
    expect(il).toEqual(['LD A', 'OR B', 'AND NOT C', 'LD D', 'LD E', 'AND F', 'ORB', 'ANB']);
  });

  it('Omron DOL mnemonic', () => {
    const p = build('dol', { lamps: false });
    const c = new Ctx(p, 'omron', 'en');
    expect(omronMnemonic(p, c)).toEqual(['LD 0.00', 'OR 100.00', 'AND NOT 0.01', 'AND NOT 0.02', 'OUT 100.00', 'END']);
  });

  it('Mitsubishi star-delta has timers in 100 ms units', () => {
    const p = build('star-delta', { starTime: 6, gapMs: 100, lamps: false });
    const c = new Ctx(p, 'fx3', 'en');
    const il = mitsubishiIL(p, c, 'fx3').map((r) => r.join(' '));
    expect(il).toContain('OUT T0 K60');
    expect(il).toContain('OUT T1 K1');
    expect(il[0]).toBe('LD X0');
    expect(il.at(-1)).toBe('END');
  });

  it('Mitsubishi addresses are octal', () => {
    const p = build('sequential', { motors: 8 });
    const a = resolveAddresses(p, 'fx3');
    expect(a[tagId(p, 'KM8')]).toBe('Y7');
    const extra = { ...p, tags: [...p.tags, ...Array.from({ length: 9 }, (_, i) => ({ id: 'x' + i, name: 'x' + i, kind: 'output' as const }))] };
    expect(resolveAddresses(extra, 'fx3')['x0']).toBe('Y10');
  });

  it('all targets export every template without crashing', () => {
    for (const t of TEMPLATES) {
      const p = t.build(defaults(t), 'en');
      for (const target of TARGETS) {
        const r = target.run(p, 'en');
        expect(r.files.length).toBeGreaterThan(0);
        for (const f of r.files) expect(f.content).not.toContain('???');
      }
    }
  });

  it('M221 IL uses parentheses for nested branches', () => {
    const p = build('alarm');
    const r = TARGETS.find((t) => t.id === 'm221-il')!.run(p, 'en');
    expect(r.files[0].content).toMatch(/AND\(/);
    expect(r.files[1].content).toContain('%TM0: Type=TON');
  });
});
