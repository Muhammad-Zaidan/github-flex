import type { Lang } from '../i18n';
import type { AddressMap } from '../core/addressing';
import { readBit, type SimState } from '../core/simulator';
import type { Project } from '../core/types';
import { t, type Key } from './strings';

interface Props {
  lang: Lang;
  project: Project;
  addr: AddressMap;
  sim: SimState;
  onInput: (tag: string, v: boolean) => void;
  paused: boolean;
  onPause: (p: boolean) => void;
  speed: number;
  onSpeed: (s: number) => void;
  onReset: () => void;
  compact?: boolean;
}

const capture = (e: { currentTarget: Element; pointerId: number }) => { try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* synthetic pointer */ } };

export function SimPanel({ lang, project, addr, sim, onInput, paused, onPause, speed, onSpeed, onReset, compact }: Props) {
  const L = (k: Key) => t(lang, k);
  const inputs = project.tags.filter((x) => x.kind === 'input');
  const outputs = project.tags.filter((x) => x.kind === 'output' || x.kind === 'memory');
  const internals = project.tags.filter((x) => x.kind === 'timer' || x.kind === 'counter' || x.kind === 'word');
  const presets = new Map<string, number>();
  for (const r of project.rungs) for (const o of r.outputs) {
    if (o.kind === 'timer') presets.set(o.tag, o.presetMs);
    if (o.kind === 'counter') presets.set(o.tag, o.preset);
  }

  return (
    <div className={`sim ${compact ? 'compact' : ''}`}>
      <div className="sim-ctl">
        <button type="button" className="ghost sm" onClick={() => onPause(!paused)}>{paused ? L('resume') : L('pause')}</button>
        <label className="speed">
          <span>{L('speed')}</span>
          <select value={speed} onChange={(e) => onSpeed(Number(e.target.value))}>
            {[0.25, 0.5, 1, 2, 5].map((s) => <option key={s} value={s}>{s}×</option>)}
          </select>
        </label>
        <button type="button" className="ghost sm" onClick={onReset}>{L('resetSim')}</button>
      </div>

      <section aria-label={L('simInputs')}>
        <h3>{L('simInputs')}</h3>
        <div className="sim-inputs">
          {inputs.map((tg) => {
            const on = !!sim.bits[tg.id];
            const momentary = (tg.device ?? 'pushbutton') === 'pushbutton';
            return (
              <button
                key={tg.id}
                type="button"
                className={`inbtn ${on ? 'on' : ''} ${momentary ? 'pb' : 'sw'}`}
                aria-pressed={on}
                title={tg.comment}
                onPointerDown={momentary ? (e) => { capture(e); onInput(tg.id, true); } : undefined}
                onPointerUp={momentary ? () => onInput(tg.id, false) : undefined}
                onPointerCancel={momentary ? () => onInput(tg.id, false) : undefined}
                onKeyDown={momentary ? (e) => { if ((e.key === ' ' || e.key === 'Enter') && !e.repeat) { e.preventDefault(); onInput(tg.id, true); } } : undefined}
                onKeyUp={momentary ? (e) => { if (e.key === ' ' || e.key === 'Enter') onInput(tg.id, false); } : undefined}
                onClick={momentary ? undefined : () => onInput(tg.id, !on)}
              >
                <span className="led" aria-hidden />
                <span className="inname">{tg.name}</span>
                <span className="inmeta mono">{addr[tg.id]}</span>
                <span className="inmeta">{momentary ? L('hold') : L('toggle')}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section aria-label={L('simOutputs')}>
        <h3>{L('simOutputs')}</h3>
        <ul className="lamps">
          {outputs.map((tg) => {
            const on = readBit(sim, tg.id);
            return (
              <li key={tg.id} className={on ? 'on' : ''} title={tg.comment}>
                <span className={`lamp ${tg.kind}`} aria-hidden />
                <span className="lname">{tg.name}</span>
                <span className="mono lad">{addr[tg.id]}</span>
                <span className="sr">{on ? 'ON' : 'OFF'}</span>
              </li>
            );
          })}
        </ul>
      </section>

      {internals.length > 0 && !compact && (
        <section aria-label={L('simInternal')}>
          <h3>{L('simInternal')}</h3>
          <ul className="internals">
            {internals.map((tg) => {
              if (tg.kind === 'timer') {
                const s = sim.timers[tg.id];
                const pt = presets.get(tg.id) ?? 0;
                return (
                  <li key={tg.id} className={s?.done ? 'on' : ''}>
                    <span className="lname">{tg.name}</span>
                    <span className="meter"><span style={{ width: `${pt ? Math.min(100, ((s?.acc ?? 0) / pt) * 100) : 0}%` }} /></span>
                    <span className="mono">{((s?.acc ?? 0) / 1000).toFixed(1)} / {(pt / 1000).toFixed(1)} s</span>
                  </li>
                );
              }
              if (tg.kind === 'counter') {
                const s = sim.counters[tg.id];
                const pv = presets.get(tg.id) ?? 0;
                return (
                  <li key={tg.id} className={s?.done ? 'on' : ''}>
                    <span className="lname">{tg.name}</span>
                    <span className="meter"><span style={{ width: `${pv ? Math.min(100, ((s?.cv ?? 0) / pv) * 100) : 0}%` }} /></span>
                    <span className="mono">{s?.cv ?? 0} / {pv}</span>
                  </li>
                );
              }
              return (
                <li key={tg.id}>
                  <span className="lname">{tg.name}</span>
                  <span className="mono">{sim.words[tg.id] ?? 0}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
      {!compact && <p className="field-h">{L('simHint')}</p>}
    </div>
  );
}
