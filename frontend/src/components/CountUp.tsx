/**
 * Animates a numeric value from `from` to `to` over `duration` ms
 * using requestAnimationFrame. Used for weight / age / counts in
 * hero cards — gives a small "alive" feel on mount.
 *
 * Respects prefers-reduced-motion: when set, the component renders
 * the final value immediately.
 */

import { useEffect, useRef, useState } from 'react';

interface CountUpProps {
  to: number;
  duration?: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

export function CountUp({ to, duration = 600, decimals = 1, suffix = '', className }: CountUpProps) {
  const [value, setValue] = useState(to);
  const fromRef = useRef(to);
  const startedAtRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // Respect reduced motion — jump straight to target.
    if (typeof window !== 'undefined' &&
        window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
      setValue(to);
      return;
    }

    fromRef.current = value;
    startedAtRef.current = null;

    const step = (now: number) => {
      if (startedAtRef.current == null) startedAtRef.current = now;
      const t = Math.min(1, (now - startedAtRef.current) / duration);
      // ease-out cubic — fast start, slow landing.
      const eased = 1 - Math.pow(1 - t, 3);
      const next = fromRef.current + (to - fromRef.current) * eased;
      setValue(next);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);

    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
    // We intentionally only animate on `to` change; the initial render
    // also runs the animation, which gives the "tick from 0" feel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [to]);

  return (
    <span className={className}>
      {value.toFixed(decimals)}{suffix}
    </span>
  );
}
