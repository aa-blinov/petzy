import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { duplicateOf, IntakeDeclined, logIntakeAsking } from '../../src/utils/duplicateIntake'

const mocks = vi.hoisted(() => ({ confirm: vi.fn(), logIntake: vi.fn() }))

vi.mock('../../src/services/medications.service', () => ({
  medicationsService: { logIntake: mocks.logIntake },
}))

vi.mock('antd-mobile', async (importOriginal) => {
  const actual = await importOriginal<typeof import('antd-mobile')>()
  return { ...actual, Dialog: { ...actual.Dialog, confirm: mocks.confirm } }
})

vi.hoisted(() => {
  // В этом окружении у jsdom нет хранилища, а очередь отметок живёт в нём
  class MemoryStorage {
    private map = new Map<string, string>()
    getItem(key: string) {
      return this.map.has(key) ? (this.map.get(key) as string) : null
    }
    setItem(key: string, value: string) {
      this.map.set(key, String(value))
    }
    removeItem(key: string) {
      this.map.delete(key)
    }
    clear() {
      this.map.clear()
    }
    key(index: number) {
      return [...this.map.keys()][index] ?? null
    }
    get length() {
      return this.map.size
    }
  }
  Object.defineProperty(globalThis, 'localStorage', {
    value: new MemoryStorage(),
    configurable: true,
    writable: true,
  })
})

const STORAGE_KEY = 'petzy:pendingIntakes'
const input = { date: '2026-10-20', time: '08:00' }

const answered = (status: number, data?: unknown) =>
  new AxiosError('ответ сервера', 'ERR_BAD_RESPONSE', undefined, undefined, {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: {} },
  } as unknown as AxiosResponse)

const noAnswer = () => new AxiosError('нет связи', 'ERR_NETWORK')

const duplicate = (existing: Record<string, unknown>) =>
  answered(409, { code: 'duplicate_intake', existing })

const question = () => mocks.confirm.mock.calls[0][0] as { title: string; content: string }

beforeEach(() => {
  mocks.logIntake.mockReset()
  mocks.confirm.mockReset()
  mocks.confirm.mockResolvedValue(true)
  mocks.logIntake.mockResolvedValue({ id: 'i1', ran_out: false })
  localStorage.clear()
})

describe('duplicateOf', () => {
  it('409 с кодом duplicate_intake отдаёт уже записанную отметку', () => {
    const existing = { date: '2026-10-20', time: '08:00', username: 'bob', own: false }
    expect(duplicateOf(duplicate(existing))).toEqual(existing)
  })

  it('409 с другим кодом не считается дублем', () => {
    expect(duplicateOf(answered(409, { code: 'other', existing: { date: '2026-10-20' } }))).toBeNull()
  })

  it('409 без самой отметки не считается дублем', () => {
    expect(duplicateOf(answered(409, { code: 'duplicate_intake' }))).toBeNull()
  })

  it('другой ответ сервера не считается дублем', () => {
    expect(duplicateOf(answered(400))).toBeNull()
  })

  it('ошибка без ответа сервера не считается дублем', () => {
    expect(duplicateOf(noAnswer())).toBeNull()
  })
})

describe('logIntakeAsking', () => {
  it('отметка без связи остаётся в очереди под своим логином', async () => {
    mocks.logIntake.mockRejectedValueOnce(noAnswer())
    const result = await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(result.queued).toBe(true)
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    expect(stored).toHaveLength(1)
    expect(stored[0]).toMatchObject({ owner: 'alice', medicationId: 'm1', name: 'Синулокс' })
  })

  it('без логина отметка не хранится: ошибка идёт дальше', async () => {
    mocks.logIntake.mockRejectedValueOnce(noAnswer())
    await expect(logIntakeAsking('m1', 'Синулокс', input, 'Рекс', null)).rejects.toBeTruthy()
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')).toHaveLength(0)
  })

  it('о дубле спрашивают и, получив согласие, пишут ещё раз', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false }))
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(mocks.confirm).toHaveBeenCalledTimes(1)
    expect(mocks.logIntake).toHaveBeenCalledTimes(2)
    expect(mocks.logIntake.mock.calls[1][1]).toMatchObject({ force: true })
  })

  it('отказ от второго раза оставляет журнал без изменений', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false }))
    mocks.confirm.mockResolvedValue(false)
    await expect(logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')).rejects.toBeInstanceOf(IntakeDeclined)
    expect(mocks.logIntake).toHaveBeenCalledTimes(1)
  })

  it('своя отметка в вопросе названа словом «вами»', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: 'alice', own: true }))
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(question().content).toContain('вами')
  })

  it('чужая отметка в вопросе названа именем', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false }))
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(question().content).toContain('bob')
  })

  it('чужая отметка без имени в вопросе названа обобщённо', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: null, own: false }))
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(question().content).toContain('другой человек')
  })

  it('слот по расписанию спрашивает про это время', async () => {
    mocks.logIntake.mockRejectedValueOnce(
      duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false, slot: true }),
    )
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(question().title).toBe('Это время уже отмечено')
  })

  it('столкновение по времени спрашивает про сам приём', async () => {
    mocks.logIntake.mockRejectedValueOnce(
      duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false, slot: false }),
    )
    await logIntakeAsking('m1', 'Синулокс', input, 'Рекс', 'alice')
    expect(question().title).toBe('Приём уже отмечен')
  })

  it('отметка с силой вопроса не задаёт: ошибка идёт дальше', async () => {
    mocks.logIntake.mockRejectedValueOnce(duplicate({ date: '2026-10-20', time: '08:00', username: 'bob', own: false }))
    await expect(logIntakeAsking('m1', 'Синулокс', { ...input, force: true }, 'Рекс', 'alice')).rejects.toBeTruthy()
    expect(mocks.confirm).not.toHaveBeenCalled()
  })
})
