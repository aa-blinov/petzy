import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'

const mocks = vi.hoisted(() => ({ remove: vi.fn() }))

vi.mock('../../src/services/api', () => ({
  default: { delete: mocks.remove, defaults: { baseURL: '/api' } },
  httpStatus: () => undefined,
}))

import { deleteMedicationWithUndo, medicationDeleteText } from '../../src/utils/medicationDelete'
import { closeSnackbar, getSnackbar, runSnackbarAction } from '../../src/utils/snackbar'

const KEYS: readonly unknown[][] = [
  ['medications', 'pet1'],
  ['medical-card', 'pet1'],
  ['timeline', 'pet1'],
  ['history-timeline', 'pet1'],
  ['stats', 'pet1'],
  ['pet-summary', 'pet1'],
  ['pets'],
]

/** Клиент запросов, который только записывает, что перезапрошено */
function recorder() {
  const invalidated: unknown[][] = []
  const client = {
    invalidateQueries: (opts: { predicate?: (q: { queryKey: readonly unknown[] }) => boolean }) => {
      invalidated.push(...KEYS.filter((key) => !opts.predicate || opts.predicate({ queryKey: key })))
      return Promise.resolve()
    },
  } as unknown as QueryClient
  return { client, invalidated }
}

const ACTION_MS = 6000

beforeEach(() => {
  mocks.remove.mockReset()
  mocks.remove.mockResolvedValue(undefined)
  vi.useFakeTimers()
})

afterEach(async () => {
  // Полоса с отменой должна уйти, иначе следующий тест не сможет поднять свою
  const bar = getSnackbar()
  if (bar) {
    if (bar.action) await runSnackbarAction(bar.id)
    else closeSnackbar(bar.id)
  }
  vi.useRealTimers()
})

describe('medicationDeleteText', () => {
  it('вопрос называет курс', () => {
    expect(medicationDeleteText('Синулокс')).toContain('Синулокс')
  })

  it('в вопросе сказано, чем курс сохранить', () => {
    expect(medicationDeleteText('Синулокс')).toContain('Завершить курс')
  })

  it('в вопросе сказано, что удаление можно отменить', () => {
    expect(medicationDeleteText('Синулокс')).toContain('Отменить')
  })
})

describe('deleteMedicationWithUndo', () => {
  it('сразу после удаления сервер ещё не спрашивается: отмена ещё возможна', () => {
    const { client } = recorder()
    deleteMedicationWithUndo({ _id: 'm1', name: 'Синулокс' }, client)
    expect(mocks.remove).not.toHaveBeenCalled()
  })

  it('после времени отмены сервер получает путь курса', async () => {
    const { client } = recorder()
    deleteMedicationWithUndo({ _id: 'm1', name: 'Синулокс' }, client)
    await vi.advanceTimersByTimeAsync(ACTION_MS)
    expect(mocks.remove).toHaveBeenCalledWith('/medications/m1')
  })

  it('после удаления обновляется список курсов и лента', async () => {
    const { client, invalidated } = recorder()
    deleteMedicationWithUndo({ _id: 'm1', name: 'Синулокс' }, client)
    await vi.advanceTimersByTimeAsync(ACTION_MS)
    expect(invalidated).toContainEqual(['medications', 'pet1'])
    expect(invalidated).toContainEqual(['timeline', 'pet1'])
  })

  it('неудача сервера говорит, что курс остался на месте', async () => {
    const { client } = recorder()
    mocks.remove.mockRejectedValue(new Error('нет связи'))
    deleteMedicationWithUndo({ _id: 'm1', name: 'Синулокс' }, client)
    await vi.advanceTimersByTimeAsync(ACTION_MS)
    expect(getSnackbar()?.message).toContain('Не удалось удалить «Синулокс»')
  })

  it('два удалённых подряд ждут в одной полосе и уходят вместе', async () => {
    const { client } = recorder()
    deleteMedicationWithUndo({ _id: 'm1', name: 'А' }, client)
    deleteMedicationWithUndo({ _id: 'm2', name: 'Б' }, client)
    expect(getSnackbar()?.message).toBe('Удалено: 2')
    await vi.advanceTimersByTimeAsync(ACTION_MS)
    expect(mocks.remove.mock.calls.map((call) => call[0])).toEqual(['/medications/m1', '/medications/m2'])
  })
})
