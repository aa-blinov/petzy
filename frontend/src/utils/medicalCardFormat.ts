import type { MedicalCard } from '../services/medicalCard.service';

/** A date of the card as the Russian reader writes it: 04.10.2026. */
export const formatDate = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('ru-RU');

/** Is there anything about food and living in the profile (the card says nothing about it otherwise). */
export const hasLife = (profile: MedicalCard['profile']) => !!(profile.diet || profile.living || profile.reproduction);

/** «+0,4 кг с 03.10.2026»: how the weight moved since the one before the latest («Без изменений с …» when it did not), or nothing for a single weighing. */
export function weightDelta(series: { date: string; value: number }[]): string | null {
  if (series.length < 2) return null;
  const last = series[series.length - 1];
  const before = series[series.length - 2];
  const diff = Math.round((last.value - before.value) * 100) / 100;
  if (diff === 0) return `Без изменений с ${formatDate(before.date)}`;
  const sign = diff > 0 ? '+' : diff < 0 ? '−' : '';
  return `${sign}${Math.abs(diff).toLocaleString('ru-RU')} кг с ${formatDate(before.date)}`;
}
