import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  formatDate,
  formatTime,
  getCurrentDate,
  getCurrentTime,
  parseDateTime,
  utcMoment,
  utcStampToLocal,
} from '../../src/utils/dateUtils'

// Время сервера приходит в UTC, а показывается на часах устройства
const ALMATY = 'Asia/Almaty'

beforeEach(() => {
  vi.stubEnv('TZ', ALMATY)
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.useRealTimers()
})

describe('formatDate', () => {
  it('месяц и день дополняются нулём', () => {
    expect(formatDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('formatTime', () => {
  it('часы и минуты дополняются нулём', () => {
    expect(formatTime(new Date(2026, 0, 5, 7, 5))).toBe('07:05')
  })
})

describe('utcMoment', () => {
  it('stamp без зоны читается как UTC', () => {
    expect(utcMoment('2026-10-02 07:29').toISOString()).toBe('2026-10-02T07:29:00.000Z')
  })

  it('stamp с Z читается как тот же момент', () => {
    expect(utcMoment('2026-10-02T07:29:00Z').toISOString()).toBe('2026-10-02T07:29:00.000Z')
  })

  it('stamp со своей зоной читается по ней', () => {
    expect(utcMoment('2026-10-02T07:29:00+03:00').toISOString()).toBe('2026-10-02T04:29:00.000Z')
  })
})

describe('utcStampToLocal', () => {
  it('момент из UTC показывается на часах устройства', () => {
    expect(utcStampToLocal('2026-10-02 07:29')).toBe('2026-10-02 12:29')
  })

  it('stamp с Z показывается на часах устройства', () => {
    expect(utcStampToLocal('2026-10-02T07:29:00Z')).toBe('2026-10-02 12:29')
  })

  it('нечитаемый stamp остаётся как был', () => {
    expect(utcStampToLocal('не дата')).toBe('не дата')
  })
})

describe('parseDateTime', () => {
  it('дата и время собираются в местный момент устройства', () => {
    const at = parseDateTime('2026-10-02', '07:29')
    expect(at.getFullYear()).toBe(2026)
    expect(at.getMonth()).toBe(9)
    expect(at.getDate()).toBe(2)
    expect(at.getHours()).toBe(7)
    expect(at.getMinutes()).toBe(29)
  })
})

describe('getCurrentDate и getCurrentTime', () => {
  it('сейчас читается с часов устройства', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-02T07:29:00Z'))
    expect(getCurrentDate()).toBe('2026-10-02')
    expect(getCurrentTime()).toBe('12:29')
  })
})
