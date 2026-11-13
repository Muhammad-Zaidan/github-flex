import { contact, newTag, parallel, rung, series, uid } from '../core/model';
import type {
  Coil, CompareOp, Counter, InputDevice, LogicNode, MathBox, MathOp, Operand, OutputEl, Project, Rung, Tag, Timer,
} from '../core/types';
import type { Lang } from '../i18n';

/** Small builder so templates read like the ladder they describe. */
export class B {
  tags: Tag[] = [];
  rungs: Rung[] = [];
  constructor(public lang: Lang) {}
  L = (id: string, en: string) => (this.lang === 'id' ? id : en);

  private tag(kind: Tag['kind'], name: string, comment: string, device?: InputDevice) {
    const t = newTag(kind, name, comment);
    if (kind === 'input') t.device = device ?? 'pushbutton';
    this.tags.push(t);
    return t.id;
  }
  input = (name: string, comment: string, device: InputDevice = 'pushbutton') => this.tag('input', name, comment, device);
  output = (name: string, comment: string) => this.tag('output', name, comment);
  mem = (name: string, comment: string) => this.tag('memory', name, comment);
  timer = (name: string, comment: string) => this.tag('timer', name, comment);
  counter = (name: string, comment: string) => this.tag('counter', name, comment);
  word = (name: string, comment: string) => this.tag('word', name, comment);

  r(logic: LogicNode[], outputs: OutputEl[], title: string, comment: string) {
    this.rungs.push(rung(logic, outputs, title, comment));
  }

  project(name: string, description: string, templateId: string): Project {
    return { version: 1, name, description, tags: this.tags, rungs: this.rungs, templateId };
  }
}

export const NO = (t: string) => contact(t, 'NO');
export const NC = (t: string) => contact(t, 'NC');
export const P = (t: string) => contact(t, 'P');
export const N = (t: string) => contact(t, 'N');
export const OR = (...b: (LogicNode | LogicNode[])[]) => parallel(...b.map((x) => (Array.isArray(x) ? series(...x) : x)));
export const AND = (...n: LogicNode[]) => series(...n);
export const CMP = (a: Operand, op: CompareOp, b: Operand): LogicNode => ({ kind: 'compare', id: uid('k'), op, a, b });

export const OUT = (t: string): Coil => ({ kind: 'coil', id: uid('o'), tag: t, mode: 'out' });
export const SET = (t: string): Coil => ({ kind: 'coil', id: uid('o'), tag: t, mode: 'set' });
export const RST = (t: string): Coil => ({ kind: 'coil', id: uid('o'), tag: t, mode: 'reset' });
export const TON = (t: string, ms: number): Timer => ({ kind: 'timer', id: uid('o'), tag: t, type: 'TON', presetMs: ms });
export const CTU = (t: string, preset: number, reset?: string): Counter => ({ kind: 'counter', id: uid('o'), tag: t, type: 'CTU', preset, reset });
export const MATH = (op: MathOp, out: string, a: Operand, b?: Operand): MathBox => ({ kind: 'math', id: uid('o'), op, out, a, b });
export const tag = (t: string): Operand => ({ tag: t });
export const k = (v: number): Operand => ({ value: v });
