// Generic, brand-neutral ladder model.
// A rung is a series/parallel tree of conditions that drives one or more outputs.
// This shape maps 1:1 onto instruction-list (LD/AND/OR/ANB/ORB) for every brand.

export type TagKind = 'input' | 'output' | 'memory' | 'timer' | 'counter' | 'word';

/** How an input behaves in the simulator. */
export type InputDevice = 'pushbutton' | 'switch' | 'sensor';

export interface Tag {
  id: string;
  name: string;
  kind: TagKind;
  comment?: string;
  device?: InputDevice; // inputs only
  /** Manual address per brand. When absent the address is assigned automatically. */
  address?: Partial<Record<BrandId, string>>;
}

export type ContactType = 'NO' | 'NC' | 'P' | 'N';

export interface Contact {
  kind: 'contact';
  id: string;
  tag: string; // Tag.id
  type: ContactType;
}

export type CompareOp = '=' | '<>' | '>' | '>=' | '<' | '<=';
export type Operand = { tag: string } | { value: number };

export interface Compare {
  kind: 'compare';
  id: string;
  op: CompareOp;
  a: Operand;
  b: Operand;
}

export interface Series {
  kind: 'series';
  id: string;
  items: LogicNode[];
}

export interface Parallel {
  kind: 'parallel';
  id: string;
  branches: LogicNode[];
}

export type Leaf = Contact | Compare;
export type LogicNode = Leaf | Series | Parallel;

export type CoilMode = 'out' | 'set' | 'reset';

export interface Coil {
  kind: 'coil';
  id: string;
  tag: string;
  mode: CoilMode;
}

export type TimerType = 'TON' | 'TOF' | 'TP';

export interface Timer {
  kind: 'timer';
  id: string;
  tag: string; // timer tag
  type: TimerType;
  presetMs: number;
}

export type CounterType = 'CTU' | 'CTD';

export interface Counter {
  kind: 'counter';
  id: string;
  tag: string; // counter tag
  type: CounterType;
  preset: number;
  reset?: string; // tag id whose ON state resets the counter
}

export type MathOp = 'MOV' | 'ADD' | 'SUB' | 'MUL' | 'DIV' | 'INC' | 'DEC';

export interface MathBox {
  kind: 'math';
  id: string;
  op: MathOp;
  a: Operand;
  b?: Operand;
  out: string; // word tag
}

export type OutputEl = Coil | Timer | Counter | MathBox;
export type Element = Leaf | OutputEl;

export interface Rung {
  id: string;
  /** Short title, e.g. "Self-holding KM1" */
  title?: string;
  /** Plain-language explanation of what this rung does. */
  comment?: string;
  logic: Series;
  outputs: OutputEl[];
}

export interface Project {
  version: 1;
  name: string;
  description?: string;
  tags: Tag[];
  rungs: Rung[];
  templateId?: string;
}

export type BrandId = 'omron' | 'fx3' | 'fx5' | 'm221' | 'iec';
