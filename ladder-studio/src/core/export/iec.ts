import type { Leaf, LogicNode, Operand, Project } from '../types';
import { Ctx, rootNode, slug, xmlEscape, type ExportResult, type ExportTarget } from './common';

/* ---------------- Structured Text (IEC 61131-3) ---------------- */

interface StProgram { decls: string[]; body: string[]; ctx: Ctx }

function stOperand(c: Ctx, o: Operand | undefined): string {
  if (!o) return '0';
  if ('value' in o) return String(o.value);
  const k = c.kind(o.tag);
  if (k === 'timer') return `TIME_TO_INT(${c.a(o.tag)}.ET) / 100`;
  if (k === 'counter') return `${c.a(o.tag)}.CV`;
  return c.a(o.tag);
}

function stBit(c: Ctx, tagId: string): string {
  const k = c.kind(tagId);
  return k === 'timer' || k === 'counter' ? `${c.a(tagId)}.Q` : c.a(tagId);
}

export function buildST(p: Project, c: Ctx): StProgram {
  const decls: string[] = [];
  const body: string[] = [];
  const edgeDecls: string[] = [];
  const timerType = new Map<string, string>();
  const counterType = new Map<string, string>();
  for (const r of p.rungs) for (const o of r.outputs) {
    if (o.kind === 'timer') timerType.set(o.tag, o.type);
    if (o.kind === 'counter') counterType.set(o.tag, o.type === 'CTU' ? 'CTU' : 'CTD');
  }
  for (const t of p.tags) {
    const cm = t.comment ? ` (* ${t.comment.replace(/\*\)/g, '')} *)` : '';
    const type = t.kind === 'timer' ? timerType.get(t.id) ?? 'TON' : t.kind === 'counter' ? counterType.get(t.id) ?? 'CTU' : t.kind === 'word' ? 'INT' : 'BOOL';
    decls.push(`    ${c.a(t.id)} : ${type};${cm}`);
  }

  p.rungs.forEach((r, ri) => {
    const pre: string[] = [];
    const expr = (n: LogicNode, top = true): string => {
      if (n.kind === 'series') {
        const s = n.items.map((x) => expr(x, false)).join(' AND ');
        return top || n.items.length < 2 ? s : `(${s})`;
      }
      if (n.kind === 'parallel') return `(${n.branches.map((x) => expr(x, false)).join(' OR ')})`;
      return leaf(n);
    };
    const leaf = (l: Leaf): string => {
      if (l.kind === 'compare') return `(${stOperand(c, l.a)} ${l.op} ${stOperand(c, l.b)})`;
      const v = stBit(c, l.tag);
      if (l.type === 'NO') return v;
      if (l.type === 'NC') return `NOT ${v}`;
      const inst = `${l.type === 'P' ? 'RT' : 'FT'}_${ri + 1}_${edgeDecls.length + 1}`;
      edgeDecls.push(`    ${inst} : ${l.type === 'P' ? 'R_TRIG' : 'F_TRIG'};`);
      pre.push(`${inst}(CLK := ${v});`);
      return `${inst}.Q`;
    };
    const root = rootNode(r.logic);
    const cond = root ? expr(root) : 'TRUE';
    const clean = (s?: string) => (s ?? '').replace(/\(\*|\*\)/g, '');
    body.push(`(* ${ri + 1}. ${clean(r.title)}${r.comment ? ' - ' + clean(r.comment) : ''} *)`);
    body.push(...pre);
    const multi = r.outputs.length > 1;
    const c0 = multi ? `rung${ri + 1}` : cond;
    if (multi) { decls.push(`    rung${ri + 1} : BOOL;`); body.push(`rung${ri + 1} := ${cond};`); }
    for (const o of r.outputs) {
      switch (o.kind) {
        case 'coil':
          if (o.mode === 'out') body.push(`${c.a(o.tag)} := ${c0};`);
          else body.push(`IF ${c0} THEN ${c.a(o.tag)} := ${o.mode === 'set' ? 'TRUE' : 'FALSE'}; END_IF;`);
          break;
        case 'timer':
          body.push(`${c.a(o.tag)}(IN := ${c0}, PT := T#${o.presetMs}MS);`);
          break;
        case 'counter': {
          const rs = o.reset ? stBit(c, o.reset) : 'FALSE';
          body.push(o.type === 'CTU'
            ? `${c.a(o.tag)}(CU := ${c0}, RESET := ${rs}, PV := ${o.preset});`
            : `${c.a(o.tag)}(CD := ${c0}, LOAD := ${rs}, PV := ${o.preset});`);
          break;
        }
        case 'math': {
          const d = c.a(o.out);
          const a = stOperand(c, o.a), b = stOperand(c, o.b);
          const rhs = { MOV: a, ADD: `${a} + ${b}`, SUB: `${a} - ${b}`, MUL: `${a} * ${b}`, DIV: `${a} / ${b}`, INC: `${d} + 1`, DEC: `${d} - 1` }[o.op];
          body.push(`IF ${c0} THEN ${d} := ${rhs}; END_IF;`);
          break;
        }
      }
    }
    body.push('');
  });
  return { decls: [...decls, ...edgeDecls], body, ctx: c };
}

export const stTarget: ExportTarget = {
  id: 'iec-st',
  brand: 'iec',
  software: 'IEC 61131-3 Structured Text',
  format: { id: 'Structured Text (.st)', en: 'Structured Text (.st)' },
  verified: false,
  howTo: [
    { id: 'Buat POU Program bertipe ST di software IEC (Machine Expert, CODESYS, OpenPLC, TIA SCL dengan sedikit penyesuaian).', en: 'Create an ST Program POU in your IEC software (Machine Expert, CODESYS, OpenPLC, TIA SCL with minor tweaks).' },
    { id: 'Salin blok VAR ke deklarasi, dan sisanya ke badan program.', en: 'Copy the VAR block into the declarations and the rest into the body.' },
    { id: 'Petakan variabel ke I/O fisik (AT %IX… atau I/O mapping).', en: 'Map the variables to physical I/O (AT %IX… or the I/O mapping).' },
  ],
  run(p, lang): ExportResult {
    const c = new Ctx(p, 'iec', lang);
    const st = buildST(p, c);
    const text = ['PROGRAM Main', 'VAR', ...st.decls, 'END_VAR', '', ...st.body, 'END_PROGRAM'].join('\n');
    return { files: [{ name: `${slug(p.name)}.st`, mime: 'text/plain', content: text }], warnings: c.warnings };
  },
};

/* ---------------- PLCopen XML (TC6 v2.01) with an ST body ---------------- */

export const plcopenTarget: ExportTarget = {
  id: 'plcopen',
  brand: 'iec',
  software: 'Machine Expert / SoMachine (M241/M251/M262), CODESYS',
  format: { id: 'PLCopen XML', en: 'PLCopen XML' },
  verified: false,
  howTo: [
    { id: 'Di Machine Expert/SoMachine: Project → Import PLCopenXML…, lalu pilih file .xml.', en: 'In Machine Expert/SoMachine: Project → Import PLCopenXML… and pick the .xml file.' },
    { id: 'Centang POU "Main" lalu OK. POU masuk ke Application.', en: 'Tick the "Main" POU and press OK. It is added to the Application.' },
    { id: 'Tambahkan Main ke MAST task, lalu petakan variabel ke I/O di konfigurasi I/O.', en: 'Add Main to the MAST task and map the variables to I/O in the I/O configuration.' },
    { id: 'Versi ini berisi ST. Badan program dalam bentuk Ladder (LD) menyusul di tahap native export.', en: 'This version contains ST. A Ladder (LD) body follows in the native-export stage.' },
  ],
  run(p, lang): ExportResult {
    const c = new Ctx(p, 'iec', lang);
    const st = buildST(p, c);
    const varXml = st.decls.map((d) => {
      const m = d.match(/^\s*(\w+)\s*:\s*(\w+);(?:\s*\(\*\s*(.*?)\s*\*\))?/);
      if (!m) return '';
      const [, name, type, doc] = m;
      const elem = ['BOOL', 'INT'].includes(type) ? `<${type}/>` : `<derived name="${type}"/>`;
      return `          <variable name="${name}"><type>${elem}</type>${doc ? `<documentation><xhtml xmlns="http://www.w3.org/1999/xhtml">${xmlEscape(doc)}</xhtml></documentation>` : ''}</variable>`;
    }).join('\n');
    const now = new Date().toISOString().replace(/\.\d+Z$/, '');
    const xml = `<?xml version="1.0" encoding="utf-8"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0201">
  <fileHeader companyName="" productName="Rangkai" productVersion="0.1" creationDateTime="${now}"/>
  <contentHeader name="${xmlEscape(p.name)}" modificationDateTime="${now}">
    <coordinateInfo>
      <fbd><scaling x="1" y="1"/></fbd>
      <ld><scaling x="1" y="1"/></ld>
      <sfc><scaling x="1" y="1"/></sfc>
    </coordinateInfo>
  </contentHeader>
  <types>
    <dataTypes/>
    <pous>
      <pou name="Main" pouType="program">
        <interface>
          <localVars>
${varXml}
          </localVars>
        </interface>
        <body>
          <ST><xhtml xmlns="http://www.w3.org/1999/xhtml">${xmlEscape(st.body.join('\n'))}</xhtml></ST>
        </body>
      </pou>
    </pous>
  </types>
  <instances><configurations/></instances>
</project>
`;
    return { files: [{ name: `${slug(p.name)}-plcopen.xml`, mime: 'application/xml', content: xml }], warnings: c.warnings };
  },
};
