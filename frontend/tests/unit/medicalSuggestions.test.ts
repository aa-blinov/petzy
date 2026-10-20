import { describe, expect, it } from 'vitest'
import {
  addInterval,
  daysBetween,
  DEFAULT_REPEAT,
  OCCASION_GROUPS,
  PARASITE_PRODUCTS,
  parasiteTargetOf,
  REPEAT_CHOICES,
} from '../../src/utils/medicalSuggestions'

describe('parasiteTargetOf', () => {
  it('по названию находит, от чего лекарство', () => {
    expect(parasiteTargetOf('Бравекто')).toBe('fleas_ticks')
    expect(parasiteTargetOf('Дронтал Плюс')).toBe('worms')
    expect(parasiteTargetOf('Адвокат')).toBe('both')
  })

  it('название без учёта регистра и пробелов', () => {
    expect(parasiteTargetOf('  брАвЕкто  ')).toBe('fleas_ticks')
  })

  it('незнакомое название ничего не значит', () => {
    expect(parasiteTargetOf('Байер')).toBeNull()
  })

  it('пустое название ничего не значит', () => {
    expect(parasiteTargetOf('')).toBeNull()
    expect(parasiteTargetOf('   ')).toBeNull()
  })

  it('каждое предложенное лекарство знает свою цель', () => {
    for (const product of PARASITE_PRODUCTS) {
      expect(parasiteTargetOf(product.name)).toBe(product.target)
    }
  })
})

describe('addInterval', () => {
  it('прибавляет месяцы', () => {
    expect(addInterval('2026-01-15', { months: 3 })).toBe('2026-04-15')
  })

  it('прибавляет годы', () => {
    expect(addInterval('2026-01-15', { years: 1 })).toBe('2027-01-15')
  })

  it('последний день месяца уходит в конец следующего', () => {
    expect(addInterval('2026-01-31', { months: 1 })).toBe('2026-02-28')
  })

  it('в високосном году последний день месяца берёт двадцать девятое', () => {
    expect(addInterval('2028-01-31', { months: 1 })).toBe('2028-02-29')
  })

  it('месяцы и годы складываются', () => {
    expect(addInterval('2026-01-15', { months: 6, years: 1 })).toBe('2027-07-15')
  })

  it('без интервала дата не меняется', () => {
    expect(addInterval('2026-01-15', {})).toBe('2026-01-15')
  })
})

describe('daysBetween', () => {
  it('считает дни между датами', () => {
    expect(daysBetween('2026-01-01', '2026-01-31')).toBe(30)
  })

  it('считает и назад', () => {
    expect(daysBetween('2026-01-31', '2026-01-01')).toBe(-30)
  })

  it('одинаковые даты дают ноль', () => {
    expect(daysBetween('2026-01-01', '2026-01-01')).toBe(0)
  })
})

describe('повторы', () => {
  it('у прививки год, у обработки три месяца', () => {
    expect(DEFAULT_REPEAT.vaccination).toEqual({ years: 1 })
    expect(DEFAULT_REPEAT.parasite).toEqual({ months: 3 })
  })

  it('у каждого вида с повтором есть кнопки', () => {
    for (const kind of Object.keys(DEFAULT_REPEAT)) {
      expect(REPEAT_CHOICES[kind as keyof typeof REPEAT_CHOICES]?.length).toBeGreaterThan(0)
    }
  })

  it('кнопки повтора ведут к тому же интервалу, что и обычный', () => {
    const choices = REPEAT_CHOICES.vaccination ?? []
    const defaultChoice = choices.find((c) => c.years === DEFAULT_REPEAT.vaccination?.years)
    expect(defaultChoice).toBeTruthy()
  })
})

describe('подсказки визита', () => {
  it('у визита и процедуры есть группы', () => {
    expect(OCCASION_GROUPS.visit.length).toBeGreaterThan(0)
    expect(OCCASION_GROUPS.procedure.length).toBeGreaterThan(0)
  })

  it('в каждой группе есть подсказки', () => {
    for (const groups of [OCCASION_GROUPS.visit, OCCASION_GROUPS.procedure]) {
      for (const group of groups) {
        expect(group.label).toBeTruthy()
        expect(group.items.length).toBeGreaterThan(0)
      }
    }
  })
})
