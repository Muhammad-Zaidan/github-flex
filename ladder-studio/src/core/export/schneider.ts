import type { Leaf, LogicNode, Operand, Project } from '../types';
import { Ctx, csvCell, rootNode, slug, type ExportResult, type ExportTarget } from './common';

function bit(c: Ctx, tagId: string): string {
  const k = c.kind(tagId);
  if (k === 'timer') return `${c.a(tagId)}.Q`;
  if (k === 'counter') return `${c.a(tagId)}.D`;
  return c.a(tagId);
}

function word(c: Ctx, o: Operand | undefined): string {
  if (!o) return '0';
  if ('value' in o) return String(o.value);
  const k = c.kind(o.tag);
  return k === 'timer' || k === 'counter' ? `${c.a(o.tag)}.V` : c.a(o.tag);
}

/** Schneider IL with parentheses: LD / AND / OR / AND( … ). */
export function m221Logic(c: Ctx, n: LogicNode | null): string[] {
  if (!n) { c.warn('Rung tanpa kondisi diexport dengan %S6 sebagai pengganti "selalu ON". Periksa ulang.', 'A rung without conditions uses %S6 as an "always on" stand-in. Review it.'); return ['LD %S6']; }
  const out: string[] = [];
  const leafLine = (op: string, l: Leaf) => {
    if (l.kind === 'compare') return `${op} [${word(c, l.a)} ${l.op} ${word(c, l.b)}]`;
    const sfx = l.type === 'NC' ? 'N' : l.type === 'P' ? 'R' : l.type === 'N' ? 'F' : '';
    return `${op}${sfx} ${bit(c, l.tag)}`;
  };
  const isLeaf = (x: LogicNode): x is Leaf => x.kind === 'contact' || x.kind === 'compare';
  const gen = (x: LogicNode, op: string) => {
    if (isLeaf(x)) { out.push(leafLine(op, x)); return; }
    const kids = x.kind === 'series' ? x.items : x.branches;
    const join = x.kind === 'series' ? 'AND' : 'OR';
    kids.forEach((k, i) => {
      if (i === 0) gen(k, op);
      else if (isLeaf(k)) out.push(leafLine(join, k));
      else group(join, k);
    });
  };
  const group = (op: string, x: LogicNode) => {
    // first operand inside the parenthesis is loaded implicitly: "AND( %I0.1"
    const start = out.length;
    gen(x, `${op}(`);
    const first = out[start];
    const m = first.match(/^(AND|OR)\(([NRF]?) (.*)$/);
    if (m && m[2]) {
      out[start] = `${m[1]}(`;
      out.splice(start + 1, 0, `LD${m[2]} ${m[3]}`);
      c.warn('Ada grup paralel/seri yang diawali kontak NC atau tepi. Cek penulisan "AND(" di Machine Expert Basic.', 'A parallel/series group starts with an NC or edge contact. Check the "AND(" lines in Machine Expert Basic.');
    } else if (first.startsWith(`${op}( [`)) {
      out[start] = `${op}(`;
      out.splice(start + 1, 0, `LD ${first.slice(op.length + 2)}`);
    }
    out.push(')');
  };
  gen(n, 'LD');
  return out;
}

export function m221IL(p: Project, c: Ctx): { il: string[]; config: string[] } {
  const il: string[] = [];
  const config: string[] = [];
  for (const r of p.rungs) {
    const logic = m221Logic(c, rootNode(r.logic));
    const simple = r.outputs.filter((o) => o.kind === 'coil' || o.kind === 'math');
    if (simple.length || r.outputs.length === 0) {
      il.push(...logic);
      for (const o of simple) {
        if (o.kind === 'coil') il.push(`${o.mode === 'out' ? 'ST' : o.mode === 'set' ? 'S' : 'R'} ${c.a(o.tag)}`);
        else if (o.kind === 'math') {
          const d = c.a(o.out), a = word(c, o.a), b = word(c, o.b);
          const expr = { MOV: a, ADD: `${a} + ${b}`, SUB: `${a} - ${b}`, MUL: `${a} * ${b}`, DIV: `${a} / ${b}`, INC: '', DEC: '' }[o.op];
          il.push(o.op === 'INC' ? `[INC ${d}]` : o.op === 'DEC' ? `[DEC ${d}]` : `[${d} := ${expr}]`);
        }
      }
      il.push('');
    }
    for (const o of r.outputs) {
      if (o.kind === 'timer') {
        const a = c.a(o.tag);
        il.push(`BLK ${a}`, ...logic, 'IN', 'END_BLK', '');
        const base = o.presetMs % 1000 === 0 ? 1000 : o.presetMs % 100 === 0 ? 100 : 10;
        config.push(`${a}: Type=${o.type}, Time base=${base === 1000 ? '1 s' : base + ' ms'}, Preset=${Math.round(o.presetMs / base)}`);
      }
      if (o.kind === 'counter') {
        const a = c.a(o.tag);
        il.push(`BLK ${a}`);
        if (o.reset) il.push(`LD ${bit(c, o.reset)}`, 'R');
        il.push(...logic, o.type === 'CTU' ? 'CU' : 'CD', 'END_BLK', '');
        config.push(`${a}: Preset=${o.preset}`);
      }
    }
  }
  return { il, config };
}

export const m221Target: ExportTarget = {
  id: 'm221-il',
  brand: 'm221',
  software: 'Machine Expert Basic / SoMachine Basic',
  format: { id: 'Instruction List + konfigurasi timer/counter', en: 'Instruction List + timer/counter configuration' },
  verified: false,
  howTo: [
    { id: 'Buat proyek di Machine Expert Basic, lalu pilih controller TM221 yang sesuai.', en: 'Create a project in Machine Expert Basic and choose your TM221 controller.' },
    { id: 'Di tab Programming, ubah rung ke mode IL (klik kanan rung → IL). Satu blok teks (dipisah baris kosong) sama dengan satu rung.', en: 'In Programming, switch a rung to IL (right-click the rung → IL). Each text block (separated by a blank line) is one rung.' },
    { id: 'Atur preset setiap %TM/%C sesuai file konfigurasi (Tools → Timers/Counters).', en: 'Set each %TM/%C preset from the configuration file (Tools → Timers/Counters).' },
    { id: 'Isi simbol dari file -symbols.csv (Tools → Symbol list).', en: 'Fill in symbols from the -symbols.csv file (Tools → Symbol list).' },
  ],
  run(p, lang): ExportResult {
    const c = new Ctx(p, 'm221', lang);
    const { il, config } = m221IL(p, c);
    const sym = ['Address,Symbol,Comment']
      .concat(p.tags.map((t) => [c.a(t.id), t.name, t.comment ?? ''].map(csvCell).join(',')))
      .join('\r\n');
    return {
      files: [
        { name: `${slug(p.name)}-m221.il.txt`, mime: 'text/plain', content: il.join('\r\n') },
        { name: `${slug(p.name)}-m221-config.txt`, mime: 'text/plain', content: config.join('\r\n') || '-' },
        { name: `${slug(p.name)}-m221-symbols.csv`, mime: 'text/csv', content: sym },
      ],
      warnings: c.warnings,
    };
  },
};
