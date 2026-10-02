/** Bounds that hold whatever an older install stored for the field (the server keeps the same table in
 *  web/builtin_event_types.py): a weight of 0 kg draws a false point on the chart, 99999 g is a slip of the finger.
 *  event type key, then field name: [lowest, highest]. */
const HARD_BOUNDS: Record<string, Record<string, [number, number]>> = {
  weight: { weight: [0.01, 100] },
  feeding: { food_weight: [0.1, 5000] },
};

export function hardBounds(type: string | undefined, field: string): [number, number] | null {
  return (type && HARD_BOUNDS[type]?.[field]) || null;
}

/** «0,01», «5 000»: a number the way a person reads it in an error. */
export function shown(n: number): string {
  return n.toLocaleString('ru-RU');
}
