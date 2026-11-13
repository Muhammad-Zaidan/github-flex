import {
  contact, findElement, findNode, findParent, insertAt, newTag, removeNode, replaceNode, rung, uid, type InsertWhere,
} from '../core/model';
import type { ContactType, Element, LogicNode, OutputEl, Project, Rung, Tag, TagKind } from '../core/types';

export type LeafTool = 'NO' | 'NC' | 'P' | 'N' | 'compare';
export type OutTool = 'coil' | 'set' | 'reset' | 'timer' | 'counter' | 'math';

const PREFIX: Record<TagKind, string> = { input: 'I', output: 'Q', memory: 'M', timer: 'T', counter: 'C', word: 'D' };

export function nextTagName(p: Project, kind: TagKind): string {
  const used = new Set(p.tags.map((t) => t.name));
  for (let i = 1; ; i++) if (!used.has(`${PREFIX[kind]}${i}`)) return `${PREFIX[kind]}${i}`;
}

function withNewTag(p: Project, kind: TagKind): [Project, Tag] {
  const t = newTag(kind, nextTagName(p, kind));
  return [{ ...p, tags: [...p.tags, t] }, t];
}

const mapRung = (p: Project, id: string, f: (r: Rung) => Rung): Project => ({ ...p, rungs: p.rungs.map((r) => (r.id === id ? f(r) : r)) });

/** Insert a new condition. Returns new project and the id of the inserted element. */
export function addLeaf(p: Project, tool: LeafTool, rungId: string, targetId: string | null, where: InsertWhere): [Project, string] {
  let proj = p;
  let node: LogicNode;
  if (tool === 'compare') {
    let w = p.tags.find((t) => t.kind === 'word');
    if (!w) [proj, w] = withNewTag(proj, 'word');
    node = { kind: 'compare', id: uid('k'), op: '>=', a: { tag: w.id }, b: { value: 0 } };
  } else {
    let t: Tag;
    [proj, t] = withNewTag(proj, 'input');
    node = contact(t.id, tool as ContactType);
  }
  const r = proj.rungs.find((x) => x.id === rungId)!;
  const valid = targetId && (targetId === r.logic.id || findNode(r.logic, targetId)) ? targetId : null;
  proj = mapRung(proj, rungId, (x) => ({ ...x, logic: insertAt(x.logic, valid, node, valid ? where : 'after') }));
  return [proj, node.id];
}

export function addOutput(p: Project, tool: OutTool, rungId: string): [Project, string] {
  let proj = p;
  let el: OutputEl;
  if (tool === 'timer') {
    let t: Tag; [proj, t] = withNewTag(proj, 'timer');
    el = { kind: 'timer', id: uid('o'), tag: t.id, type: 'TON', presetMs: 5000 };
  } else if (tool === 'counter') {
    let t: Tag; [proj, t] = withNewTag(proj, 'counter');
    el = { kind: 'counter', id: uid('o'), tag: t.id, type: 'CTU', preset: 10 };
  } else if (tool === 'math') {
    let w = p.tags.find((t) => t.kind === 'word');
    if (!w) [proj, w] = withNewTag(proj, 'word');
    el = { kind: 'math', id: uid('o'), op: 'INC', a: { tag: w.id }, out: w.id };
  } else {
    const kind: TagKind = tool === 'coil' ? 'output' : 'memory';
    let t: Tag; [proj, t] = withNewTag(proj, tool === 'coil' ? 'output' : kind);
    el = { kind: 'coil', id: uid('o'), tag: t.id, mode: tool === 'coil' ? 'out' : tool };
  }
  proj = mapRung(proj, rungId, (r) => ({ ...r, outputs: [...r.outputs, el] }));
  return [proj, el.id];
}

export function deleteElement(p: Project, id: string): Project {
  const f = findElement(p, id);
  if (!f) return p;
  if (f.isOutput) return mapRung(p, f.rung.id, (r) => ({ ...r, outputs: r.outputs.filter((o) => o.id !== id) }));
  if (id === f.rung.logic.id) return mapRung(p, f.rung.id, (r) => ({ ...r, logic: { ...r.logic, items: [] } }));
  return mapRung(p, f.rung.id, (r) => ({ ...r, logic: removeNode(r.logic, id) }));
}

export function patchElement(p: Project, id: string, patch: Partial<Element>): Project {
  const f = findElement(p, id);
  if (!f) return p;
  if (f.isOutput) {
    return mapRung(p, f.rung.id, (r) => ({ ...r, outputs: r.outputs.map((o) => (o.id === id ? ({ ...o, ...patch } as OutputEl) : o)) }));
  }
  return mapRung(p, f.rung.id, (r) => ({ ...r, logic: replaceNode(r.logic, id, { ...(f.el as LogicNode), ...patch } as LogicNode) }));
}

export function parentGroupId(p: Project, id: string): string | null {
  const f = findElement(p, id);
  if (!f || f.isOutput) return null;
  const par = findParent(f.rung.logic, id);
  return par ? par.id : null;
}

export const patchTag = (p: Project, id: string, patch: Partial<Tag>): Project =>
  ({ ...p, tags: p.tags.map((t) => (t.id === id ? { ...t, ...patch } : t)) });

export const addTag = (p: Project, kind: TagKind): [Project, Tag] => withNewTag(p, kind);

export function moveRung(p: Project, id: string, d: -1 | 1): Project {
  const i = p.rungs.findIndex((r) => r.id === id);
  const j = i + d;
  if (i < 0 || j < 0 || j >= p.rungs.length) return p;
  const rs = [...p.rungs];
  [rs[i], rs[j]] = [rs[j], rs[i]];
  return { ...p, rungs: rs };
}

function reId<T>(x: T): T {
  const j = JSON.parse(JSON.stringify(x));
  const walk = (o: unknown) => {
    if (Array.isArray(o)) o.forEach(walk);
    else if (o && typeof o === 'object') {
      const r = o as Record<string, unknown>;
      if (typeof r.id === 'string' && typeof r.kind === 'string') r.id = uid('d');
      Object.values(r).forEach(walk);
    }
  };
  walk(j);
  return j;
}

export function duplicateRung(p: Project, id: string): [Project, string] {
  const i = p.rungs.findIndex((r) => r.id === id);
  const copy = { ...reId(p.rungs[i]), id: uid('r') };
  const rs = [...p.rungs];
  rs.splice(i + 1, 0, copy);
  return [{ ...p, rungs: rs }, copy.id];
}

export function insertRung(p: Project, afterId?: string): [Project, string] {
  const r = rung([], []);
  const rs = [...p.rungs];
  const i = afterId ? rs.findIndex((x) => x.id === afterId) : rs.length - 1;
  rs.splice(i + 1, 0, r);
  return [{ ...p, rungs: rs }, r.id];
}

export function deleteRung(p: Project, id: string): Project {
  const rs = p.rungs.filter((r) => r.id !== id);
  return { ...p, rungs: rs.length ? rs : [rung([], [])] };
}

export const patchRung = (p: Project, id: string, patch: Partial<Rung>): Project => mapRung(p, id, (r) => ({ ...r, ...patch }));
