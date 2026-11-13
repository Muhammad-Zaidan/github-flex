import type {
  Contact, ContactType, Element, LogicNode, OutputEl, Parallel, Project, Rung, Series, Tag, TagKind,
} from './types';

let counter = 0;
export function uid(prefix = 'e'): string {
  counter = (counter + 1) % 1_000_000;
  return `${prefix}${Date.now().toString(36)}${counter.toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;
}

export const contact = (tag: string, type: ContactType = 'NO'): Contact => ({ kind: 'contact', id: uid('c'), tag, type });
export const series = (...items: LogicNode[]): Series => ({ kind: 'series', id: uid('s'), items });
export const parallel = (...branches: LogicNode[]): Parallel => ({ kind: 'parallel', id: uid('p'), branches });

export function rung(logic: LogicNode[] | Series, outputs: OutputEl[], title?: string, comment?: string): Rung {
  const s = Array.isArray(logic) ? series(...logic) : logic;
  return { id: uid('r'), title, comment, logic: s, outputs };
}

export function emptyProject(name = 'Proyek baru'): Project {
  return { version: 1, name, tags: [], rungs: [rung([], [])] };
}

export function newTag(kind: TagKind, name: string, comment?: string): Tag {
  return { id: uid('t'), kind, name, comment, ...(kind === 'input' ? { device: 'pushbutton' as const } : {}) };
}

export function isLeaf(n: LogicNode | Element): n is Extract<Element, { kind: 'contact' | 'compare' }> {
  return n.kind === 'contact' || n.kind === 'compare';
}

/** Depth-first list of logic leaves in left-to-right order. */
export function leaves(n: LogicNode): LogicNode[] {
  if (n.kind === 'series') return n.items.flatMap(leaves);
  if (n.kind === 'parallel') return n.branches.flatMap(leaves);
  return [n];
}

export function findNode(root: LogicNode, id: string): LogicNode | undefined {
  if (root.id === id) return root;
  const kids = root.kind === 'series' ? root.items : root.kind === 'parallel' ? root.branches : [];
  for (const k of kids) {
    const f = findNode(k, id);
    if (f) return f;
  }
  return undefined;
}

export function findParent(root: LogicNode, id: string): Series | Parallel | undefined {
  const kids = root.kind === 'series' ? root.items : root.kind === 'parallel' ? root.branches : [];
  for (const k of kids) {
    if (k.id === id) return root as Series | Parallel;
    const f = findParent(k, id);
    if (f) return f;
  }
  return undefined;
}

/** Collapse single-child groups, merge nested series/parallel of the same kind, drop empties. */
export function normalize(n: LogicNode): LogicNode | null {
  if (n.kind === 'series') {
    const items: LogicNode[] = [];
    for (const k of n.items) {
      const m = normalize(k);
      if (!m) continue;
      if (m.kind === 'series') items.push(...m.items);
      else items.push(m);
    }
    if (items.length === 0) return null;
    if (items.length === 1) return items[0];
    return { ...n, items };
  }
  if (n.kind === 'parallel') {
    const branches: LogicNode[] = [];
    for (const k of n.branches) {
      const m = normalize(k);
      if (!m) continue;
      if (m.kind === 'parallel') branches.push(...m.branches);
      else branches.push(m);
    }
    if (branches.length === 0) return null;
    if (branches.length === 1) return branches[0];
    return { ...n, branches };
  }
  return n;
}

/** Normalise a rung's root so it is always a Series (possibly empty). */
export function normalizeRoot(s: Series): Series {
  const m = normalize(s);
  if (!m) return { ...s, items: [] };
  if (m.kind === 'series') return { ...m, id: s.id };
  return { ...s, items: [m] };
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function mapTree(n: LogicNode, f: (n: LogicNode) => LogicNode): LogicNode {
  const m = f(n);
  if (m.kind === 'series') return { ...m, items: m.items.map((k) => mapTree(k, f)) };
  if (m.kind === 'parallel') return { ...m, branches: m.branches.map((k) => mapTree(k, f)) };
  return m;
}

export type InsertWhere = 'before' | 'after' | 'parallel';

/** Insert `node` relative to target id (target may be a leaf or a group). Returns new root. */
export function insertAt(root: Series, targetId: string | null, node: LogicNode, where: InsertWhere): Series {
  const r = clone(root);
  if (!targetId || r.items.length === 0) {
    r.items.push(node);
    return normalizeRoot(r);
  }
  if (targetId === r.id) {
    if (where === 'parallel') return normalizeRoot({ ...r, items: [parallel(series(...r.items), node)] });
    if (where === 'before') r.items.unshift(node);
    else r.items.push(node);
    return normalizeRoot(r);
  }
  const parent = findParent(r, targetId)!;
  const replace = (target: LogicNode): LogicNode[] | LogicNode => {
    if (where === 'parallel') {
      if (parent.kind === 'parallel') return [target, node];
      return parallel(target, node);
    }
    if (parent.kind === 'series') return where === 'before' ? [node, target] : [target, node];
    // parent is parallel: build a series inside this branch
    return where === 'before' ? series(node, target) : series(target, node);
  };
  const out = mapTree(r, (n) => {
    if (n.id !== parent.id) return n;
    const kids = n.kind === 'series' ? n.items : (n as Parallel).branches;
    const nextKids: LogicNode[] = [];
    for (const k of kids) {
      if (k.id === targetId) {
        const rep = replace(k);
        if (Array.isArray(rep)) nextKids.push(...rep);
        else nextKids.push(rep);
      } else nextKids.push(k);
    }
    return n.kind === 'series' ? { ...n, items: nextKids } : { ...n, branches: nextKids };
  }) as Series;
  return normalizeRoot(out);
}

export function removeNode(root: Series, id: string): Series {
  const strip = (n: LogicNode): LogicNode => {
    if (n.kind === 'series') return { ...n, items: n.items.filter((k) => k.id !== id).map(strip) };
    if (n.kind === 'parallel') return { ...n, branches: n.branches.filter((k) => k.id !== id).map(strip) };
    return n;
  };
  return normalizeRoot(strip(root) as Series);
}

export function replaceNode(root: Series, id: string, next: LogicNode): Series {
  return normalizeRoot(mapTree(root, (n) => (n.id === id ? next : n)) as Series);
}

export function tagById(p: Project, id: string | undefined): Tag | undefined {
  return id ? p.tags.find((t) => t.id === id) : undefined;
}

/** All tag ids referenced anywhere in the project. */
export function usedTagIds(p: Project): Set<string> {
  const s = new Set<string>();
  const op = (o: { tag: string } | { value: number } | undefined) => { if (o && 'tag' in o) s.add(o.tag); };
  for (const r of p.rungs) {
    for (const l of leaves(r.logic)) {
      if (l.kind === 'contact') s.add(l.tag);
      if (l.kind === 'compare') { op(l.a); op(l.b); }
    }
    for (const o of r.outputs) {
      if (o.kind === 'math') { op(o.a); op(o.b); s.add(o.out); }
      else s.add(o.tag);
      if (o.kind === 'counter' && o.reset) s.add(o.reset);
    }
  }
  return s;
}

/** Find any element (leaf or output) by id across the project. */
export function findElement(p: Project, id: string): { rung: Rung; el: Element | LogicNode; isOutput: boolean } | undefined {
  for (const r of p.rungs) {
    const n = findNode(r.logic, id);
    if (n) return { rung: r, el: n, isOutput: false };
    const o = r.outputs.find((x) => x.id === id);
    if (o) return { rung: r, el: o, isOutput: true };
  }
  return undefined;
}
