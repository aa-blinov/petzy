import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { deviceTimeZone, requiredZone, toDeviceClock, wallDate, wallTime, zonedNowStamp } from '../../src/utils/timezone'

const ALMATY = 'Asia/Almaty'
const MOSCOW = 'Europe/Moscow'

beforeEach(() => {
  vi.stubEnv('TZ', ALMATY)
})

afterEach(() => {
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

describe('deviceTimeZone', () => {
  it('называется зона устройства', () => {
    expect(deviceTimeZone()).toBe(ALMATY)
  })

  it('когда браузер не называет зону, ответа нет', () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
      resolvedOptions: () => ({ timeZone: '' }),
    } as unknown as Intl.DateTimeFormat)
    expect(deviceTimeZone()).toBeUndefined()
  })
})

describe('requiredZone', () => {
  it('зона устройства идёт с отметкой', () => {
    expect(requiredZone()).toBe(ALMATY)
  })

  it('когда зоны нет, отметка идёт в UTC', () => {
    vi.spyOn(Intl, 'DateTimeFormat').mockReturnValue({
      resolvedOptions: () => ({ timeZone: '' }),
    } as unknown as Intl.DateTimeFormat)
    expect(requiredZone()).toBe('UTC')
  })
})

describe('wallDate и wallTime', () => {
  it('дата и час берутся из начала stamp, без пересчёта', () => {
    expect(wallDate('2026-10-18T08:12:33+05:00')).toBe('2026-10-18')
    expect(wallTime('2026-10-18T08:12:33+05:00')).toBe('08:12')
  })

  it('пустой stamp даёт пустые дата и час', () => {
    expect(wallDate(null)).toBe('')
    expect(wallTime(undefined)).toBe('')
  })
})

describe('zonedNowStamp', () => {
  it('момент пишется с часами устройства и его смещением', () => {
    expect(zonedNowStamp(new Date('2026-10-18T03:12:33Z'))).toBe('2026-10-18T08:12:33+05:00')
  })
})

describe('toDeviceClock', () => {
  it('отметка со своей зоной переносится на часы устройства', () => {
    expect(toDeviceClock('2026-10-18T08:12:00+03:00', MOSCOW)).toBe('2026-10-18 10:12')
  })

  it('отметка без зоны и без источника остаётся как введена', () => {
    expect(toDeviceClock('2026-10-18T08:12:00+05:00', null)).toBe('2026-10-18 08:12')
  })

  it('отметка без смещения переносится из зоны источника', () => {
    expect(toDeviceClock('2026-10-18 08:12', MOSCOW)).toBe('2026-10-18 10:12')
  })

  it('отметка без смещения и без зоны источника остаётся как введена', () => {
    expect(toDeviceClock('2026-10-18 08:12', null)).toBe('2026-10-18 08:12')
  })

  it('отметка из своей зоны не переносится', () => {
    expect(toDeviceClock('2026-10-18 08:12', ALMATY)).toBe('2026-10-18 08:12')
  })

  it('нечитаемая отметка остаётся как была', () => {
    expect(toDeviceClock('не дата', MOSCOW)).toBe('не дата')
  })
})
