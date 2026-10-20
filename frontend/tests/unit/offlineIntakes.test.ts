import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import type { QueryClient } from '@tanstack/react-query'

const mocks = vi.hoisted(() => ({ logIntake: vi.fn() }))

vi.mock('../../src/services/medications.service', () => ({
  medicationsService: { logIntake: mocks.logIntake },
}))

vi.hoisted(() => {
  // В этом окружении у jsdom нет хранилища, а очередь живёт в нём
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

const KEYS: readonly unknown[][] = [
  ['medications', 'pet1'],
  ['medical-card', 'pet1'],
  ['timeline', 'pet1'],
  ['history-timeline', 'pet1'],
  ['stats', 'pet1'],
  ['pet-summary', 'pet1'],
  ['pets'],
]

type Login = string | null | (() => string | null)

/** Клиент запросов, который помнит логин и записывает, что перезапрошено */
function sessionClient(login: Login) {
  const invalidated: unknown[][] = []
  const client = {
    getQueryData: () => {
      const name = typeof login === 'function' ? login() : login
      return name ? { username: name } : undefined
    },
    invalidateQueries: (opts: { predicate?: (q: { queryKey: readonly unknown[] }) => boolean }) => {
      invalidated.push(...KEYS.filter((key) => !opts.predicate || opts.predicate({ queryKey: key })))
      return Promise.resolve()
    },
  } as unknown as QueryClient
  return { client, invalidated }
}

const input = (time = '08:00') => ({ date: '2026-10-20', time })

const storedQueue = (): { key: string; owner?: string; medicationId: string; name: string }[] =>
  JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')

/** Чистая очередь: своё хранилище и своя память модуля */
async function loadQueue(stored?: unknown) {
  localStorage.clear()
  if (stored !== undefined) localStorage.setItem(STORAGE_KEY, JSON.stringify(stored))
  vi.resetModules()
  const queue = await import('../../src/utils/offlineIntakes')
  const snackbar = await import('../../src/utils/snackbar')
  return { queue, snackbar }
}

const noAnswer = () => new AxiosError('нет связи', 'ERR_NETWORK')

const answered = (status: number, data?: unknown) =>
  new AxiosError('ответ сервера', 'ERR_BAD_RESPONSE', undefined, undefined, {
    status,
    data,
    statusText: '',
    headers: {},
    config: { headers: {} },
  } as unknown as AxiosResponse)

beforeEach(() => {
  mocks.logIntake.mockReset()
  mocks.logIntake.mockResolvedValue({ id: 'i1', ran_out: false })
})

afterEach(() => {
  localStorage.clear()
})

describe('isOffline', () => {
  it('ошибка без ответа означает, что связи нет', async () => {
    const { queue } = await loadQueue()
    expect(queue.isOffline(noAnswer())).toBe(true)
  })

  it('ответ сервера означает, что связь была', async () => {
    const { queue } = await loadQueue()
    expect(queue.isOffline(answered(409))).toBe(false)
  })
})

describe('enqueueIntake', () => {
  it('отметка без связи остаётся в очереди под своим логином', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'Синулокс', input(), 'Рекс')
    const stored = storedQueue()
    expect(stored).toHaveLength(1)
    expect(stored[0]).toMatchObject({ owner: 'alice', medicationId: 'm1', name: 'Синулокс', petName: 'Рекс' })
  })

  it('отметка из другой вкладки не теряется', async () => {
    const other = { key: 'other', owner: 'bob', medicationId: 'm2', name: 'Найоз', input: input('09:00') }
    const { queue } = await loadQueue([other])
    // Вторая вкладка дописала в хранилище, пока эта вкладка держит своё в памяти
    const second = { ...other, key: 'other2', medicationId: 'm3' }
    localStorage.setItem(STORAGE_KEY, JSON.stringify([other, second]))
    queue.enqueueIntake('alice', 'm1', 'Синулокс', input())
    expect(storedQueue().map((entry) => entry.key)).toEqual(['other', 'other2', expect.any(String)])
  })

  it('испорченное хранилище не ломает очередь: она пустая', async () => {
    localStorage.clear()
    localStorage.setItem(STORAGE_KEY, '{не json')
    vi.resetModules()
    const fresh = await import('../../src/utils/offlineIntakes')
    fresh.enqueueIntake('alice', 'm1', 'Синулокс', input())
    expect(storedQueue()).toHaveLength(1)
  })

  it('хранилище не со списком не ломает очередь: она пустая', async () => {
    localStorage.clear()
    localStorage.setItem(STORAGE_KEY, '{"a":1}')
    vi.resetModules()
    const fresh = await import('../../src/utils/offlineIntakes')
    fresh.enqueueIntake('alice', 'm1', 'Синулокс', input())
    expect(storedQueue()).toHaveLength(1)
  })
})

describe('flushPendingIntakes', () => {
  it('свои отметки уходят по порядку, от старой к новой', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input('08:00'))
    queue.enqueueIntake('alice', 'm2', 'Б', input('09:00'))
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(mocks.logIntake.mock.calls.map((call) => call[0])).toEqual(['m1', 'm2'])
  })

  it('чужая отметка не уходит под моим логином', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('bob', 'm2', 'Б', input())
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(mocks.logIntake).not.toHaveBeenCalled()
    expect(storedQueue()).toHaveLength(1)
  })

  it('без входа очередь не трогается', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input())
    await queue.flushPendingIntakes(sessionClient(null).client)
    expect(mocks.logIntake).not.toHaveBeenCalled()
    expect(storedQueue()).toHaveLength(1)
  })

  it('отметка без ответа остаётся в очереди, и следующая не уходит', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input('08:00'))
    queue.enqueueIntake('alice', 'm2', 'Б', input('09:00'))
    mocks.logIntake.mockRejectedValueOnce(noAnswer())
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(mocks.logIntake).toHaveBeenCalledTimes(1)
    expect(storedQueue()).toHaveLength(2)
  })

  it('дубль в журнале: отметка уходит из очереди, и об этом сказано', async () => {
    const { queue, snackbar } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'Синулокс', input())
    mocks.logIntake.mockRejectedValueOnce(answered(409))
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(storedQueue()).toHaveLength(0)
    expect(snackbar.getSnackbar()?.message).toContain('отметка уже есть в журнале')
  })

  it('отказ сервера: отметка не остаётся в очереди', async () => {
    const { queue, snackbar } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'Синулокс', input())
    mocks.logIntake.mockRejectedValueOnce(answered(400))
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(storedQueue()).toHaveLength(0)
    expect(snackbar.getSnackbar()?.message).toContain('отметку не удалось отправить')
  })

  it('после отправки лента и история обновляются', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input())
    const { client, invalidated } = sessionClient('alice')
    await queue.flushPendingIntakes(client)
    expect(invalidated).toContainEqual(['timeline', 'pet1'])
    expect(invalidated).toContainEqual(['history-timeline', 'pet1'])
  })

  it('отметка без владельца достаётся тому, кто её отправил', async () => {
    const { queue } = await loadQueue([
      { key: 'k1', medicationId: 'm1', name: 'А', input: input() },
    ])
    mocks.logIntake.mockRejectedValueOnce(noAnswer())
    await queue.flushPendingIntakes(sessionClient('alice').client)
    expect(storedQueue()[0].owner).toBe('alice')
  })

  it('сменившийся логин останавливает отправку: чужой отметке не уйти под ним', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input('08:00'))
    queue.enqueueIntake('alice', 'm2', 'Б', input('09:00'))
    let login = 'alice'
    mocks.logIntake.mockImplementation(async () => {
      login = 'bob'
      return { id: 'i1', ran_out: false }
    })
    await queue.flushPendingIntakes(sessionClient(() => login).client)
    expect(mocks.logIntake).toHaveBeenCalledTimes(1)
  })

  it('вторая отправка во время первой не идёт', async () => {
    const { queue } = await loadQueue()
    queue.enqueueIntake('alice', 'm1', 'А', input())
    const { client } = sessionClient('alice')
    const first = queue.flushPendingIntakes(client)
    const second = queue.flushPendingIntakes(client)
    await Promise.all([first, second])
    expect(mocks.logIntake).toHaveBeenCalledTimes(1)
  })
})
