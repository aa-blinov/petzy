/**
 * The weight of a visit's day. The card's series runs old to new and holds every measurement, and the visit keeps no link to
 * the one said at it, so the answer is the last measurement of that date (the one taken most recently, as the visit is
 * written after the scales), and how many there were that day, so that the row can say when it is a guess among several.
 */
export function weightOfDay(series: { date: string; value: number }[] | undefined, date: string): { value: number; count: number } | undefined {
  const that = (series ?? []).filter((point) => point.date === date);
  if (that.length === 0) return undefined;
  return { value: that[that.length - 1].value, count: that.length };
}
