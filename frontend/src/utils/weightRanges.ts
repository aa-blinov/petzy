/** The weight range of each calendar year the readings cover: «2025: от 8,2 до 8,8 кг, 2026: 9,1 кг».
    The card's own words, not the PDF's: the interface does not put a dash between two facts. */
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
      return low === high ? `${year}: ${low} кг` : `${year}: от ${low} до ${high} кг`;
    })
    .join(', ');
}
