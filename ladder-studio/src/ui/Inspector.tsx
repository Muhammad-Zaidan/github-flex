import type { ReactNode } from 'react';
import type { Lang } from '../i18n';
import type { AddressMap } from '../core/addressing';
import { findElement } from '../core/model';
import type { Element, LogicNode, Operand, Project, Tag, TagKind } from '../core/types';
import type { InsertWhere } from '../core/model';
import { t, type Key } from './strings';

interface Props {
  lang: Lang;
  project: Project;
  addr: AddressMap;
  selected: string | null;
  onPatch: (id: string, patch: Partial<Element>) => void;
  onPatchTag: (id: string, patch: Partial<Tag>) => void;
  onNewTag: (kind: TagKind) => string;
  onInsert: (where: InsertWhere) => void;
  onDelete: () => void;
  onSelectParent: () => void;
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="field">
      <span className="field-l">{label}</span>
      {children}
      {hint && <span className="field-h">{hint}</span>}
    </label>
  );
}

export function Seg<T extends string>({ value, options, onChange, label }: { value: T; options: { v: T; l: string }[]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="seg" role="radiogroup" aria-label={label}>
      {options.map((o) => (
        <button key={o.v} type="button" role="radio" aria-checked={value === o.v} className={value === o.v ? 'on' : ''} onClick={() => onChange(o.v)}>{o.l}</button>
      ))}
    </div>
  );
}

const KINDS_FOR: Record<string, TagKind[]> = {
  contact: ['input', 'output', 'memory', 'timer', 'counter'],
  coil: ['output', 'memory'],
  timer: ['timer'],
  counter: ['counter'],
  word: ['word', 'timer', 'counter'],
  wordOut: ['word'],
  reset: ['input', 'memory', 'output'],
};

export function TagPicker({ lang, project, addr, value, kinds, onChange, onNew, allowNone, label }: {
  lang: Lang; project: Project; addr: AddressMap; value?: string; kinds: TagKind[]; onChange: (id: string | undefined) => void;
  onNew: (k: TagKind) => string; allowNone?: boolean; label: string;
}) {
  const opts = project.tags.filter((x) => kinds.includes(x.kind));
  return (
    <select
      aria-label={label}
      value={value ?? ''}
      onChange={(e) => {
        const v = e.target.value;
        if (v.startsWith('new:')) onChange(onNew(v.slice(4) as TagKind));
        else onChange(v || undefined);
      }}
    >
      {allowNone && <option value="">{t(lang, 'none')}</option>}
      {kinds.map((k) => {
        const g = opts.filter((x) => x.kind === k);
        return g.length ? (
          <optgroup key={k} label={t(lang, `k_${k}` as Key)}>
            {g.map((x) => <option key={x.id} value={x.id}>{x.name}  ({addr[x.id]})</option>)}
          </optgroup>
        ) : null;
      })}
      <optgroup label={t(lang, 'newTag')}>
        {kinds.map((k) => <option key={k} value={`new:${k}`}>+ {t(lang, `k_${k}` as Key)}</option>)}
      </optgroup>
    </select>
  );
}

function OperandField({ lang, project, addr, value, onChange, onNew, label }: {
  lang: Lang; project: Project; addr: AddressMap; value?: Operand; onChange: (o: Operand) => void; onNew: (k: TagKind) => string; label: string;
}) {
  const isConst = !value || 'value' in value;
  return (
    <Field label={label}>
      <div className="row">
        <Seg value={isConst ? 'k' : 't'} label={label} options={[{ v: 't', l: t(lang, 'tag') }, { v: 'k', l: t(lang, 'constant') }]}
          onChange={(v) => onChange(v === 'k' ? { value: 0 } : { tag: project.tags.find((x) => x.kind === 'word')?.id ?? onNew('word') })} />
        {isConst
          ? <input type="number" inputMode="numeric" aria-label={label} value={value && 'value' in value ? value.value : 0} onChange={(e) => onChange({ value: Math.trunc(Number(e.target.value) || 0) })} />
          : <TagPicker lang={lang} project={project} addr={addr} label={label} value={(value as { tag: string }).tag} kinds={KINDS_FOR.word} onChange={(id) => id && onChange({ tag: id })} onNew={onNew} />}
      </div>
    </Field>
  );
}

export function Inspector(props: Props) {
  const { lang, project, addr, selected, onPatch, onPatchTag, onNewTag, onInsert, onDelete, onSelectParent } = props;
  const L = (k: Key) => t(lang, k);
  if (!selected) return <p className="muted pad">{L('nothingSelected')}</p>;
  const f = findElement(project, selected);
  if (!f) return <p className="muted pad">{L('nothingSelected')}</p>;
  const el = f.el;
  const tagOf = (id?: string) => project.tags.find((x) => x.id === id);

  const tagFields = (tagId: string, kinds: TagKind[]) => {
    const tg = tagOf(tagId);
    return (
      <>
        <Field label={L('tag')}>
          <TagPicker lang={lang} project={project} addr={addr} label={L('tag')} value={tagId} kinds={kinds} onNew={onNewTag} onChange={(id) => id && onPatch(el.id, { tag: id } as Partial<Element>)} />
        </Field>
        {tg && (
          <div className="tagedit">
            <Field label={L('name')}>
              <input value={tg.name} onChange={(e) => onPatchTag(tg.id, { name: e.target.value })} aria-label={L('name')} />
            </Field>
            <Field label={L('comment')}>
              <input value={tg.comment ?? ''} onChange={(e) => onPatchTag(tg.id, { comment: e.target.value })} aria-label={L('comment')} />
            </Field>
            <p className="field-h">{L('address')}: <code>{addr[tg.id]}</code></p>
          </div>
        )}
      </>
    );
  };

  let fields: ReactNode = null;
  let heading = '';
  const isLogic = !f.isOutput;
  const n = el as LogicNode | Element;
  switch (n.kind) {
    case 'contact':
      heading = L(`el_${n.type}` as Key);
      fields = (
        <>
          <Field label={L('type')}>
            <Seg label={L('type')} value={n.type} onChange={(v) => onPatch(n.id, { type: v })}
              options={[{ v: 'NO', l: 'NO' }, { v: 'NC', l: 'NC' }, { v: 'P', l: '↑ P' }, { v: 'N', l: '↓ N' }]} />
          </Field>
          {tagFields(n.tag, KINDS_FOR.contact)}
        </>
      );
      break;
    case 'compare':
      heading = L('el_compare');
      fields = (
        <>
          <OperandField lang={lang} project={project} addr={addr} label={L('operandA')} value={n.a} onNew={onNewTag} onChange={(a) => onPatch(n.id, { a })} />
          <Field label={L('operation')}>
            <Seg label={L('operation')} value={n.op} onChange={(op) => onPatch(n.id, { op })}
              options={(['=', '<>', '>', '>=', '<', '<='] as const).map((v) => ({ v, l: v === '<>' ? '≠' : v === '>=' ? '≥' : v === '<=' ? '≤' : v }))} />
          </Field>
          <OperandField lang={lang} project={project} addr={addr} label={L('operandB')} value={n.b} onNew={onNewTag} onChange={(b) => onPatch(n.id, { b })} />
        </>
      );
      break;
    case 'coil':
      heading = L(n.mode === 'out' ? 'el_coil' : n.mode === 'set' ? 'el_set' : 'el_reset');
      fields = (
        <>
          <Field label={L('mode')}>
            <Seg label={L('mode')} value={n.mode} onChange={(mode) => onPatch(n.id, { mode })}
              options={[{ v: 'out', l: L('el_coil') }, { v: 'set', l: 'Set' }, { v: 'reset', l: 'Reset' }]} />
          </Field>
          {tagFields(n.tag, KINDS_FOR.coil)}
        </>
      );
      break;
    case 'timer':
      heading = L('el_timer');
      fields = (
        <>
          <Field label={L('type')}>
            <Seg label={L('type')} value={n.type} onChange={(type) => onPatch(n.id, { type })}
              options={[{ v: 'TON', l: 'TON' }, { v: 'TOF', l: 'TOF' }, { v: 'TP', l: 'TP' }]} />
          </Field>
          <Field label={`${L('preset')} (${L('seconds')})`}>
            <input type="number" inputMode="decimal" min={0.01} step={0.1} value={n.presetMs / 1000}
              onChange={(e) => onPatch(n.id, { presetMs: Math.max(10, Math.round(Number(e.target.value) * 1000) || 0) })} />
          </Field>
          {tagFields(n.tag, KINDS_FOR.timer)}
        </>
      );
      break;
    case 'counter':
      heading = L('el_counter');
      fields = (
        <>
          <Field label={L('type')}>
            <Seg label={L('type')} value={n.type} onChange={(type) => onPatch(n.id, { type })} options={[{ v: 'CTU', l: 'CTU' }, { v: 'CTD', l: 'CTD' }]} />
          </Field>
          <Field label={L('preset')}>
            <input type="number" inputMode="numeric" min={1} value={n.preset} onChange={(e) => onPatch(n.id, { preset: Math.max(1, Math.trunc(Number(e.target.value)) || 1) })} />
          </Field>
          <Field label={L('resetBy')}>
            <TagPicker lang={lang} project={project} addr={addr} label={L('resetBy')} value={n.reset} kinds={KINDS_FOR.reset} allowNone onNew={onNewTag} onChange={(id) => onPatch(n.id, { reset: id })} />
          </Field>
          {tagFields(n.tag, KINDS_FOR.counter)}
        </>
      );
      break;
    case 'math':
      heading = L('el_math');
      fields = (
        <>
          <Field label={L('operation')}>
            <select value={n.op} onChange={(e) => onPatch(n.id, { op: e.target.value as typeof n.op, b: n.b ?? { value: 1 } })}>
              {(['MOV', 'ADD', 'SUB', 'MUL', 'DIV', 'INC', 'DEC'] as const).map((o) => <option key={o}>{o}</option>)}
            </select>
          </Field>
          {n.op !== 'INC' && n.op !== 'DEC' && <OperandField lang={lang} project={project} addr={addr} label={L('operandA')} value={n.a} onNew={onNewTag} onChange={(a) => onPatch(n.id, { a })} />}
          {!['MOV', 'INC', 'DEC'].includes(n.op) && <OperandField lang={lang} project={project} addr={addr} label={L('operandB')} value={n.b} onNew={onNewTag} onChange={(b) => onPatch(n.id, { b })} />}
          <Field label={L('result')}>
            <TagPicker lang={lang} project={project} addr={addr} label={L('result')} value={n.out} kinds={KINDS_FOR.wordOut} onNew={onNewTag} onChange={(id) => id && onPatch(n.id, { out: id })} />
          </Field>
        </>
      );
      break;
    case 'series':
    case 'parallel':
      heading = L(n.kind === 'series' ? 'groupSeries' : 'groupParallel');
      fields = <p className="field-h">{L('groupHint')}</p>;
      break;
  }

  return (
    <div className="inspector">
      <h3 className="insp-h">{heading}</h3>
      {fields}
      <div className="insp-actions">
        {isLogic && (
          <>
            <button type="button" onClick={() => onInsert('before')}>{L('insertBefore')}</button>
            <button type="button" onClick={() => onInsert('after')}>{L('insertAfter')}</button>
            <button type="button" onClick={() => onInsert('parallel')}>{L('insertParallel')}</button>
            {f.rung.logic.id !== n.id && <button type="button" onClick={onSelectParent}>{L('selectParent')}</button>}
          </>
        )}
        <button type="button" className="danger" onClick={onDelete}>{L('delete')}</button>
      </div>
    </div>
  );
}
