import { useCallback, useEffect, useRef, useState } from 'react';
import type { Lang } from '../i18n';
import type { BrandId, Project } from '../core/types';

const KEY_PROJECT = 'rangkai.project.v1';
const KEY_LANG = 'rangkai.lang';
const KEY_BRAND = 'rangkai.brand';

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function save(key: string, v: unknown) {
  try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage unavailable: app still works */ }
}

export const loadProject = () => load<Project | null>(KEY_PROJECT, null);

export function usePersisted<T>(key: string, initial: T) {
  const [v, setV] = useState<T>(() => load(key, initial));
  useEffect(() => save(key, v), [key, v]);
  return [v, setV] as const;
}

export const useLang = () => {
  const guess: Lang = typeof navigator !== 'undefined' && !navigator.language?.toLowerCase().startsWith('id') ? 'en' : 'id';
  return usePersisted<Lang>(KEY_LANG, guess);
};
export const useBrand = () => usePersisted<BrandId>(KEY_BRAND, 'omron');

/** Project state with undo/redo and autosave. */
export function useProjectHistory(initial: Project) {
  const [state, setState] = useState({ past: [] as Project[], present: initial, future: [] as Project[] });
  const lastMerge = useRef<{ key: string; at: number } | null>(null);

  useEffect(() => { save(KEY_PROJECT, state.present); }, [state.present]);

  /** `mergeKey` groups rapid edits (e.g. typing in a field) into one undo step. */
  const update = useCallback((fn: (p: Project) => Project, mergeKey?: string) => {
    setState((s) => {
      const next = fn(s.present);
      if (next === s.present) return s;
      const now = Date.now();
      const merge = mergeKey && lastMerge.current?.key === mergeKey && now - lastMerge.current.at < 1200;
      lastMerge.current = mergeKey ? { key: mergeKey, at: now } : null;
      return { past: merge ? s.past : [...s.past.slice(-99), s.present], present: next, future: [] };
    });
  }, []);
  const replace = useCallback((p: Project) => setState({ past: [], present: p, future: [] }), []);
  const undo = useCallback(() => setState((s) => (s.past.length ? { past: s.past.slice(0, -1), present: s.past[s.past.length - 1], future: [s.present, ...s.future] } : s)), []);
  const redo = useCallback(() => setState((s) => (s.future.length ? { past: [...s.past, s.present], present: s.future[0], future: s.future.slice(1) } : s)), []);

  return { project: state.present, update, replace, undo, redo, canUndo: state.past.length > 0, canRedo: state.future.length > 0 };
}

export function download(name: string, content: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
