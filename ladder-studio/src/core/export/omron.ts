import { addrIndex } from '../addressing';
import type { CompareOp, Leaf, Operand, Project } from '../types';
import { Ctx, csvCell, rootNode, slug, stackIL, type ExportResult, type ExportTarget } from './common';

const pad4 = (n: number) => n.toString().padStart(4, '0');

function operand(c: Ctx, o: Operand | undefined): string {
  if (!o) return '&0';
  if ('value' in o) return `&${o.value}`;
  const k = c.kind(o.tag);
  if (k === 'timer') return `T${pad4(addrIndex(c.a(o.tag)))}`;
  if (k === 'counter') return `C${pad4(addrIndex(c.a(o.tag)))}`;
  return c.a(o.tag);
}

const cmpOp: Record<CompareOp, string> = { '=': '=', '<>': '<>', '>': '>', '>=': '>=', '<': '<', '<=': '<=' };

function leaf(c: Ctx, pos: 'LD' | 'AND' | 'OR', el: Leaf): string {
  if (el.kind === 'compare') return `${pos}${cmpOp[el.op]} ${operand(c, el.a)} ${operand(c, el.b)}`;
  const a = c.a(el.tag);
  switch (el.type) {
    case 'NO': return `${pos} ${a}`;
    case 'NC': return `${pos} NOT ${a}`;
    case 'P': return `@${pos} ${a}`;
    case 'N': return `%${pos} ${a}`;
  }
}

export function omronMnemonic(p: Project, c: Ctx): string[] {
  const lines: string[] = [];
  for (const r of p.rungs) {
    const root = rootNode(r.logic);
    const logic = root ? stackIL(root, (pos, el) => leaf(c, pos, el), 'AND LD', 'OR LD') : ['LD P_On'];
    const outs = r.outputs.filter((o) => o.kind !== 'counter');
    const counters = r.outputs.filter((o) => o.kind === 'counter');
    if (outs.length || counters.length === 0) {
      lines.push(...logic);
      for (const o of outs) {
        switch (o.kind) {
          case 'coil':
            lines.push(`${o.mode === 'out' ? 'OUT' : o.mode === 'set' ? 'SET' : 'RSET'} ${c.a(o.tag)}`);
            break;
          case 'timer': {
            if (o.type !== 'TON') c.warn(`Omron CP1 tidak punya ${o.type} bawaan; diexport sebagai TIM (on-delay). Periksa ulang logikanya.`, `Omron CP1 has no built-in ${o.type}; exported as TIM (on-delay). Review the logic.`);
            const sv = Math.round(o.presetMs / 100);
            if (sv > 9999) c.warn('Preset timer melebihi 999,9 detik dan dipotong.', 'Timer preset above 999.9 s was clipped.');
            lines.push(`TIM ${pad4(addrIndex(c.a(o.tag)))} #${pad4(Math.min(9999, Math.max(0, sv)))}`);
            break;
          }
          case 'math': {
            const d = c.a(o.out);
            if (o.op === 'MOV') lines.push(`MOV ${operand(c, o.a)} ${d}`);
            else if (o.op === 'INC') lines.push(`++ ${d}`);
            else if (o.op === 'DEC') lines.push(`-- ${d}`);
            else {
              const sym = { ADD: '+', SUB: '-', MUL: '*', DIV: '/' }[o.op];
              lines.push(`${sym} ${operand(c, o.a)} ${operand(c, o.b)} ${d}`);
              if (o.op === 'MUL' || o.op === 'DIV') c.warn('Pada Omron, * dan / menulis hasil 2 word (D dan D+1). Pastikan D+1 tidak dipakai.', 'On Omron, * and / write a 2-word result (D and D+1). Make sure D+1 is free.');
            }
            break;
          }
        }
      }
    }
    for (const o of counters) {
      if (o.kind !== 'counter') continue;
      if (o.type === 'CTD') c.warn('Counter CTD diexport sebagai CNT (counter turun bawaan Omron).', 'CTD counter exported as CNT (Omron native down-counter).');
      lines.push(...logic);
      lines.push(o.reset ? `LD ${c.a(o.reset)}` : 'LD P_Off');
      lines.push(`CNT ${pad4(addrIndex(c.a(o.tag)))} #${pad4(Math.min(9999, o.preset))}`);
    }
  }
  lines.push('END');
  return lines;
}

const omronType = (k: string) => (k === 'word' ? 'INT' : 'BOOL');

export const omronTarget: ExportTarget = {
  id: 'omron-cxp',
  brand: 'omron',
  software: 'CX-Programmer',
  format: { id: 'Mnemonic + tabel simbol', en: 'Mnemonic + symbol table' },
  verified: false,
  howTo: [
    { id: 'Buat proyek baru di CX-Programmer, lalu pilih tipe CPU (misalnya CP1E-N40).', en: 'Create a new CX-Programmer project and choose the CPU type (e.g. CP1E-N40).' },
    { id: 'Buka program, lalu tekan Alt+3 atau View → Mnemonics untuk pindah ke tampilan mnemonic.', en: 'Open the program and press Alt+3 or View → Mnemonics to switch to the mnemonic view.' },
    { id: 'Klik baris pertama, lalu paste isi file .txt. Hapus END bawaan jika jadi ganda.', en: 'Click the first row and paste the .txt contents. Remove the default END if it is duplicated.' },
    { id: 'Buka Symbols (tabel simbol lokal), lalu paste isi file .csv supaya nama dan komentar I/O ikut masuk.', en: 'Open Symbols (local symbol table) and paste the .csv contents to bring in I/O names and comments.' },
    { id: 'Kembali ke tampilan ladder (Alt+1), lalu Compile (Ctrl+F7) dan periksa errornya.', en: 'Go back to the ladder view (Alt+1), Compile (Ctrl+F7) and check for errors.' },
  ],
  run(p, lang): ExportResult {
    const c = new Ctx(p, 'omron', lang);
    const il = omronMnemonic(p, c).join('\r\n');
    const sym = ['Name,Data Type,Address,Comment']
      .concat(p.tags.map((t) => [t.name, omronType(t.kind), c.a(t.id), t.comment ?? ''].map(csvCell).join(',')))
      .join('\r\n');
    if (/^[@%]/m.test(il)) c.warn('Kontak tepi naik/turun diexport sebagai @LD/%LD (differentiated). Pastikan CPU mendukungnya.', 'Rising/falling edge contacts are exported as @LD/%LD (differentiated). Make sure your CPU supports them.');
    if (!p.rungs.some((r) => r.outputs.length || r.logic.items.length)) c.warn('Program kosong.', 'Program is empty.');
    return {
      files: [
        { name: `${slug(p.name)}-omron.txt`, mime: 'text/plain', content: il },
        { name: `${slug(p.name)}-omron-symbols.csv`, mime: 'text/csv', content: sym },
      ],
      warnings: c.warnings,
    };
  },
};
