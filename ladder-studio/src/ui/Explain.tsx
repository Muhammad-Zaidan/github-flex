import type { Lang } from '../i18n';
import type { AddressMap } from '../core/addressing';
import type { Project, Tag } from '../core/types';
import { t, type Key } from './strings';

export function Explain({ lang, project, addr, onPickRung }: { lang: Lang; project: Project; addr: AddressMap; onPickRung: (id: string) => void }) {
  const L = (k: Key) => t(lang, k);
  const io = project.tags.filter((x) => x.kind === 'input' || x.kind === 'output');
  return (
    <div className="explain">
      <section>
        <h3>{L('logicPerRung')}</h3>
        <ol className="rung-notes">
          {project.rungs.map((r, i) => (
            <li key={r.id}>
              <button type="button" className="linklike" onClick={() => onPickRung(r.id)}>
                <span className="rn">{i + 1}</span>
                <span>
                  <strong>{r.title || `${L('rung')} ${i + 1}`}</strong>
                  {r.comment && <span className="rc">{r.comment}</span>}
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>
      <section>
        <h3>{L('ioList')}</h3>
        <table className="iolist">
          <thead><tr><th>{L('address')}</th><th>{L('name')}</th><th>{L('comment')}</th></tr></thead>
          <tbody>
            {io.map((tg) => <tr key={tg.id}><td className="mono">{addr[tg.id]}</td><td>{tg.name}</td><td>{tg.comment}</td></tr>)}
          </tbody>
        </table>
      </section>
      <section>
        <h3>{L('wiring')}</h3>
        <Wiring tags={project.tags} addr={addr} />
        <p className="field-h">{L('wiringNote')}</p>
      </section>
    </div>
  );
}

/** Generic PLC wiring: inputs from +24V through devices, outputs through loads to 0V/N. */
export function Wiring({ tags, addr }: { tags: Tag[]; addr: AddressMap }) {
  const ins = tags.filter((x) => x.kind === 'input');
  const outs = tags.filter((x) => x.kind === 'output');
  const rows = Math.max(ins.length, outs.length, 1);
  const RH = 46;
  const top = 40;
  const W = 640;
  const H = top + rows * RH + 40;
  const plcX = 250, plcW = 140;
  const y = (i: number) => top + 20 + i * RH;

  const device = (tg: Tag, cx: number, cy: number) => {
    const d = tg.device ?? 'pushbutton';
    if (d === 'sensor') return (
      <g>
        <rect x={cx - 16} y={cy - 12} width={32} height={24} rx={3} className="wd" />
        <path d={`M ${cx - 7} ${cy} L ${cx + 3} ${cy - 6} M ${cx - 7} ${cy} L ${cx + 3} ${cy + 6}`} className="wd" />
      </g>
    );
    if (d === 'switch') return <path d={`M ${cx - 16} ${cy} L ${cx - 8} ${cy} L ${cx + 8} ${cy - 10} M ${cx + 8} ${cy} L ${cx + 16} ${cy}`} className="wd" />;
    return (
      <g>
        <path d={`M ${cx - 16} ${cy} L ${cx - 9} ${cy} M ${cx + 9} ${cy} L ${cx + 16} ${cy} M ${cx - 11} ${cy - 7} L ${cx + 11} ${cy - 7} M ${cx} ${cy - 7} L ${cx} ${cy - 15} M ${cx - 6} ${cy - 15} L ${cx + 6} ${cy - 15}`} className="wd" />
      </g>
    );
  };
  const load = (tg: Tag, cx: number, cy: number) => {
    if (/^H_|LAMP|LAMPU|^A_|^B_/.test(tg.name)) return (
      <g>
        <circle cx={cx} cy={cy} r={10} className="wd" />
        <path d={`M ${cx - 7} ${cy - 7} L ${cx + 7} ${cy + 7} M ${cx + 7} ${cy - 7} L ${cx - 7} ${cy + 7}`} className="wd" />
      </g>
    );
    return <rect x={cx - 12} y={cy - 9} width={24} height={18} className="wd" />;
  };

  return (
    <svg className="wiring" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="PLC wiring">
      <text x={20} y={22} className="wl">+24 VDC</text>
      <line x1={30} y1={30} x2={30} y2={H - 20} className="wr" />
      <text x={W - 60} y={22} className="wl">0V / N</text>
      <line x1={W - 30} y1={30} x2={W - 30} y2={H - 20} className="wr" />
      <rect x={plcX} y={top} width={plcW} height={rows * RH} rx={6} className="plc" />
      <text x={plcX + plcW / 2} y={top + rows * RH / 2} className="plct">PLC</text>
      {ins.map((tg, i) => (
        <g key={tg.id}>
          <line x1={30} y1={y(i)} x2={plcX} y2={y(i)} className="wwire" />
          <rect x={110} y={y(i) - 16} width={60} height={32} className="wbg" />
          {device(tg, 140, y(i))}
          <text x={60} y={y(i) - 8} className="wn">{tg.name}</text>
          <text x={plcX + 8} y={y(i) + 4} className="wa">{addr[tg.id]}</text>
          <circle cx={plcX} cy={y(i)} r={3} className="term" />
        </g>
      ))}
      {ins.length > 0 && (
        <g>
          <line x1={plcX} y1={top + rows * RH - 10} x2={W - 30} y2={top + rows * RH - 10} className="wwire thin" />
          <text x={plcX + 8} y={top + rows * RH - 14} className="wa">COM</text>
        </g>
      )}
      {outs.map((tg, i) => (
        <g key={tg.id}>
          <line x1={plcX + plcW} y1={y(i)} x2={W - 30} y2={y(i)} className="wwire" />
          <rect x={470} y={y(i) - 14} width={40} height={28} className="wbg" />
          {load(tg, 490, y(i))}
          <text x={plcX + plcW - 8} y={y(i) + 4} className="wa end">{addr[tg.id]}</text>
          <text x={522} y={y(i) - 8} className="wn">{tg.name}</text>
          <circle cx={plcX + plcW} cy={y(i)} r={3} className="term" />
        </g>
      ))}
    </svg>
  );
}
