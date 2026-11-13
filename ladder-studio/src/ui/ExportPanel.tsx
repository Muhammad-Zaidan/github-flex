import { useMemo, useState } from 'react';
import type { Lang } from '../i18n';
import { TARGETS } from '../core/export';
import type { BrandId, Project } from '../core/types';
import { download } from './store';
import { t, type Key } from './strings';

export function ExportPanel({ lang, project, brand, onBrand }: { lang: Lang; project: Project; brand: BrandId; onBrand: (b: BrandId) => void }) {
  const L = (k: Key) => t(lang, k);
  const [targetId, setTargetId] = useState(() => TARGETS.find((x) => x.brand === brand)?.id ?? TARGETS[0].id);
  const target = TARGETS.find((x) => x.id === targetId)!;
  const result = useMemo(() => target.run(project, lang), [target, project, lang]);
  const [fileIdx, setFileIdx] = useState(0);
  const [copied, setCopied] = useState(false);
  const file = result.files[Math.min(fileIdx, result.files.length - 1)];

  const pick = (id: string) => {
    setTargetId(id);
    setFileIdx(0);
    const b = TARGETS.find((x) => x.id === id)!.brand;
    if (b !== 'iec') onBrand(b);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(file.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked: the download button still works */ }
  };

  return (
    <div className="export">
      <fieldset className="targets">
        <legend>{L('target')}</legend>
        {TARGETS.map((x) => (
          <label key={x.id} className={`target ${x.id === targetId ? 'on' : ''}`}>
            <input type="radio" name="target" value={x.id} checked={x.id === targetId} onChange={() => pick(x.id)} />
            <span className="tsw">{x.software.split(',')[0]}</span>
            <span className="tfmt">{x.format[lang]}</span>
          </label>
        ))}
      </fieldset>

      {!target.verified && (
        <div className="notice amber" role="note">
          <strong>{L('unverified')}</strong>
          <span>{L('unverifiedBody')}</span>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="notice" role="note">
          <strong>{L('warnings')}</strong>
          <ul>{result.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
        </div>
      )}

      <section>
        <h3>{L('howTo')}</h3>
        <ol className="steps">{target.howTo.map((s, i) => <li key={i}>{s[lang]}</li>)}</ol>
      </section>

      <section className="files">
        <div className="filetabs" role="tablist">
          {result.files.map((f, i) => (
            <button key={f.name} role="tab" type="button" aria-selected={f === file} className={f === file ? 'on' : ''} onClick={() => setFileIdx(i)}>{f.name}</button>
          ))}
        </div>
        <pre className="code" tabIndex={0} aria-label={file.name}>{file.content}</pre>
        <div className="row gap">
          <button type="button" className="primary" onClick={() => download(file.name, file.content, file.mime)}>{L('download')} {file.name.split('.').pop()?.toUpperCase()}</button>
          <button type="button" className="ghost" onClick={copy} aria-live="polite">{copied ? L('copied') : L('copy')}</button>
          <button type="button" className="ghost" onClick={() => window.print()}>{L('printPdf')}</button>
        </div>
      </section>
      <p className="safety">{L('safety')}</p>
    </div>
  );
}
