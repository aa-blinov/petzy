import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { dayColumn, minutesAgo, nowWhen, whenLabel, whenPhrase, yesterdayEvening } from '../../src/utils/intakeWhen'

const ALMATY = 'Asia/Almaty'

beforeEach(() => {
  vi.stubEnv('TZ', ALMATY)
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-20T07:00:00Z'))
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllEnvs()
})

describe('dayColumn', () => {
  it('в списке неделя дней, от сегодняшнего к прошлому', () => {
    const days = dayColumn()
    expect(days).toHaveLength(7)
    expect(days[0].value).toBe('2026-10-20')
    expect(days[6].value).toBe('2026-10-14')
  })

  it('сегодняшний день назван сегодняшним', () => {
    expect(dayColumn()[0].label).toBe('Сегодня')
  })

  it('вчерашний день назван вчерашним', () => {
    expect(dayColumn()[1].label).toBe('Вчера')
  })

  it('день из этой недели не повторяется вторым разом', () => {
    const days = dayColumn('2026-10-16')
    expect(days).toHaveLength(7)
    expect(days.filter((day) => day.value === '2026-10-16')).toHaveLength(1)
  })

  it('день старше недели добавляется в список', () => {
    const days = dayColumn('2026-10-10')
    expect(days).toHaveLength(8)
    expect(days[7].value).toBe('2026-10-10')
    expect(days[7].label).toContain('10 окт.')
  })
})

describe('whenLabel', () => {
  it('сегодняшняя отметка называется сегодняшней', () => {
    expect(whenLabel({ date: '2026-10-20', time: '08:00' })).toBe('Сегодня, 08:00')
  })

  it('вчерашняя отметка называется вчерашней', () => {
    expect(whenLabel({ date: '2026-10-19', time: '21:30' })).toBe('Вчера, 21:30')
  })

  it('старая отметка называется датой и часом', () => {
    expect(whenLabel({ date: '2026-10-10', time: '09:15' })).toBe('сб, 10 окт., 09:15')
  })
})

describe('whenPhrase', () => {
  it('сегодняшняя отметка читается как фраза', () => {
    expect(whenPhrase({ date: '2026-10-20', time: '08:00' })).toBe('сегодня в 08:00')
  })

  it('вчерашняя отметка читается как фраза', () => {
    expect(whenPhrase({ date: '2026-10-19', time: '21:30' })).toBe('вчера в 21:30')
  })
})

describe('minutesAgo', () => {
  it('пятнадцать минут назад считаются от сейчас', () => {
    expect(minutesAgo(15)).toEqual({ date: '2026-10-20', time: '11:45' })
  })
})

describe('yesterdayEvening', () => {
  it('вчерашний вечер это вчера в 20:00', () => {
    expect(yesterdayEvening()).toEqual({ date: '2026-10-19', time: '20:00' })
  })
})

describe('nowWhen', () => {
  it('сейчас читается с часов устройства', () => {
    expect(nowWhen()).toEqual({ date: '2026-10-20', time: '12:00' })
  })
})
