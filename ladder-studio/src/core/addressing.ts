import type { BrandId, Project, Tag, TagKind } from './types';

export interface BrandInfo {
  id: BrandId;
  label: string;
  software: string;
  cpus: string;
}

export const BRANDS: BrandInfo[] = [
  { id: 'omron', label: 'Omron', software: 'CX-Programmer', cpus: 'CP1E · CP1L · CP1H · CP2E' },
  { id: 'fx3', label: 'Mitsubishi FX3', software: 'GX Works2', cpus: 'FX3U · FX3G · FX3S' },
  { id: 'fx5', label: 'Mitsubishi iQ-F', software: 'GX Works3', cpus: 'FX5U · FX5UC · FX5UJ' },
  { id: 'm221', label: 'Schneider M221', software: 'Machine Expert Basic / SoMachine Basic', cpus: 'TM221' },
  { id: 'iec', label: 'IEC 61131-3', software: 'Machine Expert / CODESYS / OpenPLC', cpus: 'M241 · M251 · M262 · lainnya' },
];

const pad = (n: number, w: number) => n.toString().padStart(w, '0');

function autoAddress(brand: BrandId, kind: TagKind, i: number, tag: Tag): string {
  switch (brand) {
    case 'omron':
      switch (kind) {
        case 'input': return `${Math.floor(i / 12)}.${pad(i % 12, 2)}`;
        case 'output': return `${100 + Math.floor(i / 8)}.${pad(i % 8, 2)}`;
        case 'memory': return `W${Math.floor(i / 16)}.${pad(i % 16, 2)}`;
        case 'timer': return `T${pad(i, 4)}`;
        case 'counter': return `C${pad(i, 4)}`;
        case 'word': return `D${i}`;
      }
      break;
    case 'fx3':
    case 'fx5':
      switch (kind) {
        case 'input': return `X${i.toString(8)}`;
        case 'output': return `Y${i.toString(8)}`;
        case 'memory': return `M${i}`;
        case 'timer': return `T${i}`;
        case 'counter': return `C${i}`;
        case 'word': return `D${i}`;
      }
      break;
    case 'm221':
      switch (kind) {
        case 'input': return `%I0.${i}`;
        case 'output': return `%Q0.${i}`;
        case 'memory': return `%M${i}`;
        case 'timer': return `%TM${i}`;
        case 'counter': return `%C${i}`;
        case 'word': return `%MW${i}`;
      }
      break;
    case 'iec':
      return symbol(tag.name);
  }
  return '?';
}

/** Make a valid IEC identifier from a human name. */
export function symbol(name: string): string {
  let s = name.normalize('NFKD').replace(/[^\w]+/g, '_').replace(/^_+|_+$/g, '');
  if (!s) s = 'X';
  if (/^\d/.test(s)) s = '_' + s;
  return s;
}

export type AddressMap = Record<string, string>;

/** Resolve every tag's address for a brand. Manual addresses win; others are packed in order. */
export function resolveAddresses(p: Project, brand: BrandId): AddressMap {
  const out: AddressMap = {};
  const used = new Set<string>();
  for (const t of p.tags) {
    const manual = t.address?.[brand]?.trim();
    if (manual) { out[t.id] = manual; used.add(manual); }
  }
  const next: Record<TagKind, number> = { input: 0, output: 0, memory: 0, timer: 0, counter: 0, word: 0 };
  for (const t of p.tags) {
    if (out[t.id]) continue;
    if (brand === 'iec') {
      let s = symbol(t.name);
      let k = 2;
      while (used.has(s)) s = `${symbol(t.name)}_${k++}`;
      out[t.id] = s; used.add(s);
      continue;
    }
    let a: string;
    do { a = autoAddress(brand, t.kind, next[t.kind]++, t); } while (used.has(a));
    out[t.id] = a; used.add(a);
  }
  return out;
}

/** Index number of a timer/counter address, e.g. "T0003" -> 3, "%TM2" -> 2. */
export function addrIndex(a: string): number {
  const m = a.match(/(\d+)$/);
  return m ? parseInt(m[1], 10) : 0;
}
