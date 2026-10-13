/** The weight range of each calendar year the readings cover, as the PDF writes it: «2025: 8,2–8,2 кг; 2026: 8,8–9,1 кг». */
export function weightRangeByYear(series: { date: string; value: number }[]): string {
  const years = new Map<string, number[]>();
  for (const point of series) {
    const year = point.date.slice(0, 4);
    years.set(year, [...(years.get(year) ?? []), point.value]);
  }
  return [...years.keys()]
    .sort()
    .map((year) => {
      const values = years.get(year) ?? [];
      const low = Math.min(...values).toLocaleString('ru-RU');
      const high = Math.max(...values).toLocaleString('ru-RU');
      return `${year}: ${low}–${high} кг`;
    })
    .join('; ');
}
