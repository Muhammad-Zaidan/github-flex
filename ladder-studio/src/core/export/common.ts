import type { Lang, Text } from '../../i18n';
import { resolveAddresses, type AddressMap } from '../addressing';
import type { BrandId, Leaf, LogicNode, Operand, Project, Tag } from '../types';

export interface ExportFile { name: string; mime: string; content: string }

export interface ExportResult {
  files: ExportFile[];
  warnings: string[];
}

export interface ExportTarget {
  id: string;
  brand: BrandId;
  software: string;
  format: Text;
  /** step-by-step import instructions */
  howTo: Text[];
  /** false until the output has been confirmed by opening it in the real software */
  verified: boolean;
  run: (p: Project, lang: Lang) => ExportResult;
}

export class Ctx {
  addr: AddressMap;
  warnings: string[] = [];
  tags: Map<string, Tag>;
  constructor(public p: Project, public brand: BrandId, public lang: Lang) {
    this.addr = resolveAddresses(p, brand);
    this.tags = new Map(p.tags.map((t) => [t.id, t]));
  }
  L = (id: string, en: string) => (this.lang === 'id' ? id : en);
  warn(id: string, en: string) {
    const m = this.L(id, en);
    if (!this.warnings.includes(m)) this.warnings.push(m);
  }
  a(tagId: string): string { return this.addr[tagId] ?? '???'; }
  kind(tagId: string) { return this.tags.get(tagId)?.kind; }
  name(tagId: string) { return this.tags.get(tagId)?.name ?? tagId; }
  isOp(o: Operand | undefined): o is { tag: string } { return !!o && 'tag' in o; }
}

/**
 * Stack-style instruction list (Omron / Mitsubishi): LD/AND/OR + block ops.
 * `leaf(pos, el)` returns one or more lines for a leaf at position LD/AND/OR.
 */
export function stackIL(
  n: LogicNode,
  leaf: (pos: 'LD' | 'AND' | 'OR', el: Leaf) => string,
  andBlock: string,
  orBlock: string,
): string[] {
  const out: string[] = [];
  const gen = (x: LogicNode) => {
    if (x.kind === 'series') {
      x.items.forEach((it, i) => {
        if (i === 0) gen(it);
        else if (it.kind === 'contact' || it.kind === 'compare') out.push(leaf('AND', it));
        else { gen(it); out.push(andBlock); }
      });
    } else if (x.kind === 'parallel') {
      x.branches.forEach((br, i) => {
        if (i === 0) gen(br);
        else if (br.kind === 'contact' || br.kind === 'compare') out.push(leaf('OR', br));
        else { gen(br); out.push(orBlock); }
      });
    } else out.push(leaf('LD', x));
  };
  gen(n);
  return out;
}

/** The rung's logic as a single node, or null when empty (always true). */
export function rootNode(s: { items: LogicNode[] }): LogicNode | null {
  if (s.items.length === 0) return null;
  if (s.items.length === 1) return s.items[0];
  return s as LogicNode;
}

export const csvCell = (s: string) => (/[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s);

export function slug(s: string) {
  return s.toLowerCase().normalize('NFKD').replace(/[^\w]+/g, '-').replace(/^-+|-+$/g, '') || 'program';
}

export function xmlEscape(s: string) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
