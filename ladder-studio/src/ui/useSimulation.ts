import { useCallback, useEffect, useRef, useState } from 'react';
import { initialState, scan, type SimState } from '../core/simulator';
import type { Project } from '../core/types';

const SCAN_MS = 10;

/** Runs the scan loop on animation frames while `active`. */
export function useSimulation(project: Project, active: boolean) {
  const [state, setState] = useState<SimState>(() => scan(project, initialState(project), 0));
  const [paused, setPaused] = useState(false);
  const [speed, setSpeed] = useState(1);
  const ref = useRef(state);
  const inputs = useRef<Record<string, boolean>>({});
  const projRef = useRef(project);

  // Restart when the program structure changes so stale state never lingers.
  useEffect(() => {
    projRef.current = project;
    const s = scan(project, { ...initialState(project), bits: { ...initialState(project).bits, ...inputs.current } }, 0);
    ref.current = s;
    setState(s);
  }, [project]);

  useEffect(() => {
    if (!active || paused) return;
    let raf = 0;
    let last = performance.now();
    let carry = 0;
    const tick = (now: number) => {
      carry += Math.min(250, now - last) * speed;
      last = now;
      let s = ref.current;
      let n = 0;
      while (carry >= SCAN_MS && n < 2000) {
        s = scan(projRef.current, { ...s, bits: { ...s.bits, ...inputs.current } }, SCAN_MS);
        carry -= SCAN_MS;
        n++;
      }
      if (n) { ref.current = s; setState(s); }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [active, paused, speed]);

  const setInput = useCallback((tag: string, v: boolean) => {
    inputs.current = { ...inputs.current, [tag]: v };
    // Scan immediately so a quick tap is never missed, even when paused.
    const s = scan(projRef.current, { ...ref.current, bits: { ...ref.current.bits, ...inputs.current } }, 0);
    ref.current = s;
    setState(s);
  }, []);

  const reset = useCallback(() => {
    inputs.current = {};
    const s = scan(projRef.current, initialState(projRef.current), 0);
    ref.current = s;
    setState(s);
  }, []);

  return { state, setInput, reset, paused, setPaused, speed, setSpeed, inputs: inputs.current };
}
