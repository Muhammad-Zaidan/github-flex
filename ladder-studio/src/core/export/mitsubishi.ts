import type { BrandId, Leaf, Operand, Project } from '../types';
import { Ctx, csvCell, rootNode, slug, stackIL, type ExportResult, type ExportTarget } from './common';

function operand(c: Ctx, o: Operand | undefined): string {
  if (!o) return 'K0';
  if ('value' in o) return `K${o.value}`;
  return c.a(o.tag); // T/C as word = current value
}

function leaf(c: Ctx, pos: 'LD' | 'AND' | 'OR', el: Leaf): string {
  if (el.kind === 'compare') return `${pos}${el.op} ${operand(c, el.a)} ${operand(c, el.b)}`;
  const a = c.a(el.tag);
  const base = pos === 'AND' ? 'AND' : pos;
  switch (el.type) {
    case 'NO': return `${base} ${a}`;
    case 'NC': return `${pos === 'LD' ? 'LDI' : pos === 'AND' ? 'ANI' : 'ORI'} ${a}`;
    case 'P': return `${base}P ${a}`;
    case 'N': return `${base}F ${a}`;
  }
}

/** Instruction list as [instruction, device...] rows. */
export function mitsubishiIL(p: Project, c: Ctx, brand: BrandId): string[][] {
  const rows: string[][] = [];
  const always = brand === 'fx5' ? 'SM400' : 'M8000';
  const split = (s: string) => s.split(' ');
  for (const r of p.rungs) {
    const root = rootNode(r.logic);
    const logic = root ? stackIL(root, (pos, el) => leaf(c, pos, el), 'ANB', 'ORB') : [`LD ${always}`];
    rows.push(...logic.map(split));
    for (const o of r.outputs) {
      switch (o.kind) {
        case 'coil':
          rows.push([o.mode === 'out' ? 'OUT' : o.mode === 'set' ? 'SET' : 'RST', c.a(o.tag)]);
          break;
        case 'timer': {
          if (o.type !== 'TON') c.warn(`Timer ${o.type} tidak tersedia sebagai instruksi dasar FX; diexport sebagai timer on-delay. Periksa ulang logikanya.`, `${o.type} is not a basic FX instruction; exported as an on-delay timer. Review the logic.`);
          rows.push(['OUT', c.a(o.tag), `K${Math.max(1, Math.round(o.presetMs / 100))}`]);
          break;
        }
        case 'counter':
          if (o.type === 'CTD') c.warn('Counter turun diexport sebagai counter naik FX (C0–C199). Periksa logikanya.', 'Down-counter exported as an FX up-counter (C0–C199). Review the logic.');
          rows.push(['OUT', c.a(o.tag), `K${o.preset}`]);
          break;
        case 'math': {
          const d = c.a(o.out);
          if (o.op === 'MOV') rows.push(['MOV', operand(c, o.a), d]);
          else if (o.op === 'INC' || o.op === 'DEC') rows.push([o.op, d]);
          else rows.push([o.op, operand(c, o.a), operand(c, o.b), d]);
          if (o.op === 'MUL') c.warn('MUL menulis hasil 32-bit (D dan D+1).', 'MUL writes a 32-bit result (D and D+1).');
          if (o.op === 'DIV') c.warn('DIV menulis hasil bagi di D dan sisa di D+1.', 'DIV writes the quotient to D and the remainder to D+1.');
          break;
        }
      }
    }
    // Counter reset is a separate rung on Mitsubishi.
    for (const o of r.outputs) {
      if (o.kind === 'counter' && o.reset) {
        rows.push(['LD', c.a(o.reset)], ['RST', c.a(o.tag)]);
      }
    }
  }
  rows.push(['END']);
  return rows;
}

function makeTarget(brand: 'fx3' | 'fx5'): ExportTarget {
  const sw = brand === 'fx3' ? 'GX Works2' : 'GX Works3';
  return {
    id: brand === 'fx3' ? 'gx2' : 'gx3',
    brand,
    software: sw,
    format: { id: 'Instruction list + CSV + daftar device', en: 'Instruction list + CSV + device comments' },
    verified: false,
    howTo: brand === 'fx3'
      ? [
          { id: 'Buat Simple Project di GX Works2, pilih seri FX3U/FX3G, bahasa Ladder.', en: 'Create a Simple Project in GX Works2, FX3U/FX3G series, Ladder language.' },
          { id: 'Cara A: di editor ladder, buka menu Edit → Read from CSV File, lalu pilih file -gxw2.csv.', en: 'Option A: in the ladder editor use Edit → Read from CSV File and pick the -gxw2.csv file.' },
          { id: 'Cara B: ketik instruksi dari file .txt langsung di ladder (ketik "LD X0" lalu Enter, dan seterusnya).', en: 'Option B: type each instruction from the .txt straight into the ladder (type "LD X0", Enter, and so on).' },
          { id: 'Import komentar device dari file -comments.csv (Device Comment → Read from CSV).', en: 'Import device comments from the -comments.csv file (Device Comment → Read from CSV).' },
          { id: 'Convert (F4), lalu periksa errornya.', en: 'Convert (F4) and check for errors.' },
        ]
      : [
          { id: 'Buat proyek baru di GX Works3, seri FX5CPU, bahasa Ladder.', en: 'Create a new GX Works3 project, FX5CPU series, Ladder language.' },
          { id: 'Buka program MAIN. Ketik instruksi dari file .txt langsung di ladder (ketik "LD X0" lalu Enter, dan seterusnya), atau coba Project → Open Other File → CSV.', en: 'Open program MAIN. Type each instruction from the .txt into the ladder ("LD X0", Enter, …), or try Project → Open Other File → CSV.' },
          { id: 'Import komentar device dari file -comments.csv (Device Comment → Import).', en: 'Import device comments from the -comments.csv file (Device Comment → Import).' },
          { id: 'Convert (F4), lalu periksa errornya.', en: 'Convert (F4) and check for errors.' },
        ],
    run(p, lang): ExportResult {
      const c = new Ctx(p, brand, lang);
      const rows = mitsubishiIL(p, c, brand);
      const txt = rows.map((r) => r.join(' ')).join('\r\n');
      // GX Works "Read from CSV File" layout: program name, PLC info, header, then rows.
      const csv = [
        `"MAIN"`,
        `"PLC Information:","${brand === 'fx3' ? 'FX3U/FX3UC' : 'FX5U'}"`,
        `"Step No.","Line Statement","Instruction","I/O(Device)","Blank","PI Statement","Note"`,
        ...rows.flatMap((r, i) => {
          const [ins, ...devs] = r;
          const first = [String(i), '', ins, devs[0] ?? '', '', '', ''];
          const more = devs.slice(1).map((d) => ['', '', '', d, '', '', '']);
          return [first, ...more].map((cols) => cols.map((x) => `"${x}"`).join(','));
        }),
      ].join('\r\n');
      const comments = ['Device,Comment']
        .concat(p.tags.map((t) => [c.a(t.id), `${t.name}${t.comment ? ' - ' + t.comment : ''}`].map(csvCell).join(',')))
        .join('\r\n');
      return {
        files: [
          { name: `${slug(p.name)}-${brand}.txt`, mime: 'text/plain', content: txt },
          { name: `${slug(p.name)}-${brand === 'fx3' ? 'gxw2' : 'gxw3'}.csv`, mime: 'text/csv', content: csv },
          { name: `${slug(p.name)}-${brand}-comments.csv`, mime: 'text/csv', content: comments },
        ],
        warnings: c.warnings,
      };
    },
  };
}

export const gx2Target = makeTarget('fx3');
export const gx3Target = makeTarget('fx5');
