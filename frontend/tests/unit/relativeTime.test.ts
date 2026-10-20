import { describe, expect, it } from 'vitest'
import { computePetAge, formatRelativeDate, formatRelativeDateTime, formatRelativeShort, pluralRu } from '../../src/utils/relativeTime'

const NOW = new Date(2026, 9, 20, 12, 0)

describe('formatRelativeDateTime', () => {
  it('сегодняшняя запись говорит сегодняшнее время', () => {
    expect(formatRelativeDateTime('2026-10-20 08:00', NOW)).toBe('сегодня в 08:00')
  })

  it('вчерашняя запись говорит вчерашнее время', () => {
    expect(formatRelativeDateTime('2026-10-19 19:00', NOW)).toBe('вчера в 19:00')
  })

  it('запись через день говорит про завтра', () => {
    expect(formatRelativeDateTime('2026-10-21 08:00', NOW)).toBe('завтра в 08:00')
  })

  it('запись впереди на несколько дней называет срок', () => {
    expect(formatRelativeDateTime('2026-10-23 08:00', NOW)).toBe('через 3 дня, 08:00')
  })

  it('внутри недели остаётся время записи', () => {
    expect(formatRelativeDateTime('2026-10-17 08:00', NOW)).toBe('3 дня назад, 08:00')
  })

  it('дальше недели время записи не показывается', () => {
    expect(formatRelativeDateTime('2026-10-13 08:00', NOW)).toBe('7 дней назад')
  })

  it('прошлый год называется датой и годом', () => {
    expect(formatRelativeDateTime('2025-09-16 08:00', NOW)).toBe('16 сентября 2025')
  })

  it('дата впереди дальше недели называется датой', () => {
    expect(formatRelativeDateTime('2026-11-05 08:00', NOW)).toBe('5 ноября в 08:00')
  })

  it('неразобранная дата остаётся как пришла', () => {
    expect(formatRelativeDateTime('не дата', NOW)).toBe('не дата')
  })
})

describe('formatRelativeDate', () => {
  it('сегодняшняя запись говорит сегодня', () => {
    expect(formatRelativeDate('2026-10-20 08:00', NOW)).toBe('сегодня')
  })

  it('вчерашняя запись говорит вчера', () => {
    expect(formatRelativeDate('2026-10-19 08:00', NOW)).toBe('вчера')
  })

  it('запись прошлой недели называется числом дней', () => {
    expect(formatRelativeDate('2026-10-17 08:00', NOW)).toBe('3 дня назад')
  })

  it('прошлый год называется датой и годом', () => {
    expect(formatRelativeDate('2025-09-16 08:00', NOW)).toBe('16 сентября 2025')
  })

  it('неразобранная дата остаётся как пришла', () => {
    expect(formatRelativeDate('не дата', NOW)).toBe('не дата')
  })
})

describe('formatRelativeShort', () => {
  it('только что: та же минута', () => {
    expect(formatRelativeShort('2026-10-20 12:00', NOW)).toBe('только что')
  })

  it('минуты назад', () => {
    expect(formatRelativeShort('2026-10-20 11:45', NOW)).toBe('15 мин назад')
  })

  it('часы назад', () => {
    expect(formatRelativeShort('2026-10-20 10:00', NOW)).toBe('2 ч назад')
  })

  it('дни назад', () => {
    expect(formatRelativeShort('2026-10-17 12:00', NOW)).toBe('3 дн назад')
  })

  it('неразобранная дата остаётся как пришла', () => {
    expect(formatRelativeShort('не дата', NOW)).toBe('не дата')
  })
})

describe('computePetAge', () => {
  it('питомцу пять лет', () => {
    expect(computePetAge('2021-05-10', NOW)).toBe('5 лет')
  })

  it('питомцу девять месяцев', () => {
    expect(computePetAge('2026-01-20', NOW)).toBe('9 месяцев')
  })

  it('новорождённому три дня', () => {
    expect(computePetAge('2026-10-17', NOW)).toBe('3 дня')
  })

  it('недельному питомцу неделя', () => {
    expect(computePetAge('2026-10-13', NOW)).toBe('1 неделя')
  })

  it('до дня рождения ещё не исполнилось целого года', () => {
    expect(computePetAge('2021-05-25', new Date(2026, 4, 20, 12, 0))).toBe('4 года')
  })

  it('без даты рождения возраст пустой', () => {
    expect(computePetAge('', NOW)).toBe('')
  })

  it('неразобранная дата рождения даёт пустой возраст', () => {
    expect(computePetAge('не дата', NOW)).toBe('')
  })

  it('дата рождения в будущем даёт пустой возраст', () => {
    expect(computePetAge('2027-01-01', NOW)).toBe('')
  })
})

describe('pluralRu', () => {
  it('один предмет говорится одним словом', () => {
    expect(pluralRu(1, 'год', 'года', 'лет')).toBe('год')
  })

  it('два предмета говорятся вторым словом', () => {
    expect(pluralRu(2, 'год', 'года', 'лет')).toBe('года')
  })

  it('пять предметов говорятся третьим словом', () => {
    expect(pluralRu(5, 'год', 'года', 'лет')).toBe('лет')
  })

  it('одиннадцать предметов говорятся третьим словом', () => {
    expect(pluralRu(11, 'год', 'года', 'лет')).toBe('лет')
  })

  it('двадцать один предмет говорится одним словом', () => {
    expect(pluralRu(21, 'год', 'года', 'лет')).toBe('год')
  })
})
