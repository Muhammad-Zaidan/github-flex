import { useEffect, useState } from 'react';
import { emptyProject } from './core/model';
import type { Project } from './core/types';
import { Editor } from './ui/Editor';
import { Home } from './ui/Home';
import { loadProject, useBrand, useLang, useProjectHistory } from './ui/store';

const route = () => (location.hash.startsWith('#/editor') ? 'editor' : 'home');

export default function App() {
  const [lang, setLang] = useLang();
  const [brand, setBrand] = useBrand();
  const [stored] = useState(loadProject);
  const hist = useProjectHistory(stored ?? emptyProject(lang === 'id' ? 'Proyek baru' : 'New project'));
  const [view, setView] = useState(route);

  useEffect(() => {
    const f = () => setView(route());
    window.addEventListener('hashchange', f);
    return () => window.removeEventListener('hashchange', f);
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  useEffect(() => {
    document.title = view === 'editor' ? `${hist.project.name} – Rangkai` : 'Rangkai: ladder PLC dari template dan simulasi';
  }, [view, hist.project.name]);

  const go = (v: 'home' | 'editor') => { location.hash = v === 'editor' ? '#/editor' : '#/'; window.scrollTo(0, 0); };
  const open = (p: Project) => { hist.replace(p); go('editor'); };
  const hasProject = !!stored || hist.canUndo || hist.project.rungs.some((r) => r.logic.items.length || r.outputs.length);

  if (view === 'editor') return <Editor lang={lang} hist={hist} brand={brand} onBrand={setBrand} onHome={() => go('home')} onLang={setLang} />;
  return (
    <Home lang={lang} onLang={setLang} hasProject={hasProject} onContinue={() => go('editor')}
      onBlank={() => open(emptyProject(lang === 'id' ? 'Proyek baru' : 'New project'))} onOpen={open} />
  );
}
