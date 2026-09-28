/** A round step for about ``target`` gaps across ``span``: 1, 2 or 5 times a power of ten. */
function niceStep(span: number, target = 4): number {
  const raw = span / target;
  const power = 10 ** Math.floor(Math.log10(raw));
  const scaled = raw / power;
  return (scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10) * power;
}

/**
 * The Y scale of a value chart, fitted to the readings. From zero, a cat
 * going from 4.2 to 4.5 kg drew a flat line at the top: the change an owner
 * looks for was a few pixels. Round bounds and ticks, a little air around
 * the data, and never below zero for readings that can't be negative.
 */
export function valueScale(values: number[]): { domain: [number, number]; ticks: number[]; decimals: number } {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo;
  // One reading, or all the same: a band around it, not a zero-height axis.
  const pad = span > 0 ? span * 0.15 : Math.max(Math.abs(hi) * 0.05, 0.5);
  const step = niceStep(span + 2 * pad);
  let bottom = Math.floor((lo - pad) / step) * step;
  if (lo >= 0 && bottom < 0) bottom = 0;
  const top = Math.ceil((hi + pad) / step) * step;
  const decimals = Math.max(0, -Math.floor(Math.log10(step)));
  const ticks: number[] = [];
  for (let tick = bottom; tick <= top + step / 2; tick += step) ticks.push(Number(tick.toFixed(decimals)));
  return { domain: [ticks[0], ticks[ticks.length - 1]], ticks, decimals };
}
