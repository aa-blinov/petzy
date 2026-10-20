import { describe, expect, it } from 'vitest'
import type { Medication } from '../../src/services/medications.service'
import { formatAmount, isAmountDraft, parseAmount, stockSummary } from '../../src/utils/stock'

const medication = (fields: Partial<Medication>): Medication =>
  ({
    _id: 'm1',
    pet_id: 'p1',
    name: 'Синулокс',
    type: 'Таблетка',
    schedule: { days: [0], times: ['08:00'] },
    inventory_enabled: true,
    inventory_current: 12,
    is_active: true,
    ...fields,
  }) as Medication

describe('formatAmount', () => {
  it('дробное число пишется с запятой', () => {
    expect(formatAmount(0.5)).toBe('0,5')
  })

  it('тысячи не разделяются пробелом: из поля не прочитать обратно', () => {
    expect(formatAmount(1000)).toBe('1000')
  })
})

describe('parseAmount', () => {
  it('запятая с клавиатуры читается как точка', () => {
    expect(parseAmount('0,5')).toBe(0.5)
  })

  it('пробелы по краям не мешают', () => {
    expect(parseAmount(' 1 ')).toBe(1)
  })

  it('пустое поле не число', () => {
    expect(parseAmount('')).toBeNull()
  })

  it('текст не число', () => {
    expect(parseAmount('abc')).toBeNull()
  })

  it('две запятые не число', () => {
    expect(parseAmount('1,2,3')).toBeNull()
  })
})

describe('isAmountDraft', () => {
  it('целое поле принимается', () => {
    expect(isAmountDraft('12')).toBe(true)
  })

  it('одна запятая в конце принимается', () => {
    expect(isAmountDraft('12,')).toBe(true)
  })

  it('одна точка в конце принимается', () => {
    expect(isAmountDraft('12.')).toBe(true)
  })

  it('две запятые не принимаются', () => {
    expect(isAmountDraft('12,,5')).toBe(false)
  })

  it('буквы не принимаются', () => {
    expect(isAmountDraft('12 мг')).toBe(false)
  })
})

describe('stockSummary', () => {
  it('без учёта остатка карточка ничего не говорит', () => {
    expect(stockSummary(medication({ inventory_enabled: false }))).toBeNull()
  })

  it('когда остаток неизвестен, карточка ничего не говорит', () => {
    expect(stockSummary(medication({ inventory_current: undefined }))).toBeNull()
  })

  it('нулевой остаток говорит, что лекарство кончилось', () => {
    const summary = stockSummary(medication({ inventory_current: 0 }))
    expect(summary?.amount).toBe('Закончилось')
    expect(summary?.tone).toBe('out')
  })

  it('остаток и единица стоят рядом', () => {
    const summary = stockSummary(medication({ inventory_current: 12, dose_unit: 'капс' }))
    expect(summary?.amount).toBe('Осталось 12 капс')
  })

  it('без своей единицы остаток считается в дозах', () => {
    const summary = stockSummary(medication({ inventory_current: 12 }))
    expect(summary?.amount).toBe('Осталось 12 доз')
  })

  it('срок хватает говорится в днях', () => {
    const summary = stockSummary(medication({ inventory_days_left: 2 }))
    expect(summary?.lasts).toContain('хватит примерно на 2 дня')
  })

  it('на один день говорится одним словом', () => {
    const summary = stockSummary(medication({ inventory_days_left: 1 }))
    expect(summary?.lasts).toContain('хватит примерно на 1 день,')
  })

  it('меньше дня говорится словами, а не числом', () => {
    const summary = stockSummary(medication({ inventory_days_left: 0.5 }))
    expect(summary?.lasts).toBe('меньше чем на день')
  })

  it('без расписания срока хватает нет', () => {
    const summary = stockSummary(medication({ inventory_days_left: null }))
    expect(summary?.lasts).toBe('')
  })

  it('заканчивающийся остаток помечается', () => {
    const summary = stockSummary(medication({ inventory_low: true }))
    expect(summary?.flag).toBe('заканчивается')
    expect(summary?.tone).toBe('low')
  })

  it('обычный остаток не помечается', () => {
    const summary = stockSummary(medication({ inventory_low: false }))
    expect(summary?.flag).toBe('')
    expect(summary?.tone).toBe('ok')
  })
})
