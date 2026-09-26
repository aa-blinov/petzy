import type { Medication } from '../services/medications.service';
import { pluralRu } from './relativeTime';

/** "12", "0,5", "1000": Russian decimals, no trailing zeros. No digit
 *  grouping: «1 000» wouldn't read back from a form field. */
export function formatAmount(value: number): string {
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 2, useGrouping: false });
}

/** A typed amount, with a comma or a dot («0,5» from a Russian keyboard). */
export function parseAmount(text: string): number | null {
  const normalized = text.trim().replace(',', '.');
  if (normalized === '') return null;
  const value = Number(normalized);
  return Number.isFinite(value) ? value : null;
}

/** What an amount field accepts while typing: digits and one , or . */
export function isAmountDraft(text: string): boolean {
  return /^\d*[.,]?\d*$/.test(text);
}

export type StockTone = 'ok' | 'low' | 'out';

export interface StockSummary {
  /** «Осталось 12 капс» or «Закончилось». */
  amount: string;
  /** «хватит примерно на 6 дней»; empty without a schedule. */
  lasts: string;
  /** A word the eye catches: «заканчивается». */
  flag: string;
  tone: StockTone;
}

/** How a course's stock reads on its card. */
export function stockSummary(med: Medication): StockSummary | null {
  if (!med.inventory_enabled || med.inventory_current == null) return null;
  const unit = med.dose_unit || 'доз';
  const current = med.inventory_current;
  if (current <= 0) {
    return { amount: 'Закончилось', lasts: '', flag: '', tone: 'out' };
  }
  const days = med.inventory_days_left;
  let lasts = '';
  if (days != null) {
    const whole = Math.floor(days);
    lasts = whole < 1 ? 'меньше чем на день' : `хватит примерно на ${whole} ${pluralRu(whole, 'день', 'дня', 'дней')}`;
  }
  const low = !!med.inventory_low;
  return {
    amount: `Осталось ${formatAmount(current)} ${unit}`,
    lasts,
    flag: low ? 'заканчивается' : '',
    tone: low ? 'low' : 'ok',
  };
}

export const RAN_OUT_MESSAGE = 'Лекарство закончилось. Пополните остаток, когда купите новое';
