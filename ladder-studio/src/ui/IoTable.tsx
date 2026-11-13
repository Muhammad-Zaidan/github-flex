import type { Lang } from '../i18n';
import { BRANDS, type AddressMap } from '../core/addressing';
import { usedTagIds } from '../core/model';
import type { BrandId, InputDevice, Project, Tag, TagKind } from '../core/types';
import { t, type Key } from './strings';

interface Props {
  lang: Lang;
  project: Project;
  brand: BrandId;
  addr: AddressMap;
  onBrand: (b: BrandId) => void;
  onPatchTag: (id: string, patch: Partial<Tag>) => void;
  onAddTag: (k: TagKind) => void;
  onDeleteTag: (id: string) => void;
}

const KINDS: TagKind[] = ['input', 'output', 'memory', 'timer', 'counter', 'word'];

export function BrandSelect({ lang, brand, onBrand }: { lang: Lang; brand: BrandId; onBrand: (b: BrandId) => void }) {
  return (
    <label className="brandsel">
      <span>{t(lang, 'addressFor')}</span>
      <select value={brand} onChange={(e) => onBrand(e.target.value as BrandId)}>
        {BRANDS.map((b) => <option key={b.id} value={b.id}>{b.label} ({b.software.split(' / ')[0]})</option>)}
      </select>
    </label>
  );
}

export function IoTable({ lang, project, brand, addr, onBrand, onPatchTag, onAddTag, onDeleteTag }: Props) {
  const L = (k: Key) => t(lang, k);
  const used = usedTagIds(project);
  const names = new Map<string, number>();
  for (const x of project.tags) names.set(x.name.trim().toUpperCase(), (names.get(x.name.trim().toUpperCase()) ?? 0) + 1);
  const dup = (n: string) => (names.get(n.trim().toUpperCase()) ?? 0) > 1;
  return (
    <div className="io">
      <div className="io-top">
        <BrandSelect lang={lang} brand={brand} onBrand={onBrand} />
        <p className="field-h">{L('addrHelp')}</p>
      </div>
      {KINDS.map((k) => {
        const rows = project.tags.filter((x) => x.kind === k);
        return (
          <section key={k} className="io-group" aria-label={L(`k_${k}` as Key)}>
            <div className="io-gh">
              <h3>{L(`k_${k}` as Key)} <span className="count">{rows.length}</span></h3>
              <button type="button" className="ghost sm" onClick={() => onAddTag(k)}>+ {L('addTag')}</button>
            </div>
            {rows.length > 0 && (
              <div className="io-rows" role="table">
                <div className="io-row io-head" role="row">
                  <span role="columnheader">{L('address')}</span>
                  <span role="columnheader">{L('name')}</span>
                  <span role="columnheader">{L('comment')}</span>
                  <span role="columnheader" className="sr">{L('delete')}</span>
                </div>
                {rows.map((tg) => (
                  <div className={`io-row ${used.has(tg.id) ? '' : 'unused'}`} role="row" key={tg.id}>
                    <input className="mono addr-in" role="cell" aria-label={`${L('address')} ${tg.name}`} placeholder={addr[tg.id]}
                      value={tg.address?.[brand] ?? ''} onChange={(e) => onPatchTag(tg.id, { address: { ...tg.address, [brand]: e.target.value } })} />
                    <input role="cell" aria-label={`${L('name')} ${tg.name}`} aria-invalid={dup(tg.name)} title={dup(tg.name) ? L('dupName') : undefined} value={tg.name} onChange={(e) => onPatchTag(tg.id, { name: e.target.value })} />
                    <div className="io-c" role="cell">
                      <input aria-label={`${L('comment')} ${tg.name}`} value={tg.comment ?? ''} onChange={(e) => onPatchTag(tg.id, { comment: e.target.value })} />
                      {k === 'input' && (
                        <select aria-label={`${L('device')} ${tg.name}`} value={tg.device ?? 'pushbutton'} onChange={(e) => onPatchTag(tg.id, { device: e.target.value as InputDevice })}>
                          <option value="pushbutton">{L('d_pushbutton')}</option>
                          <option value="switch">{L('d_switch')}</option>
                          <option value="sensor">{L('d_sensor')}</option>
                        </select>
                      )}
                      {dup(tg.name) && <span className="tagnote bad">{L('dupName')}</span>}
                      {!used.has(tg.id) && <span className="tagnote">{L('unusedTag')}</span>}
                    </div>
                    <button type="button" className="icon" role="cell" aria-label={`${L('deleteTag')} ${tg.name}`}
                      disabled={used.has(tg.id)} title={used.has(tg.id) ? L('tagInUse') : L('deleteTag')} onClick={() => onDeleteTag(tg.id)}>×</button>
                  </div>
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
