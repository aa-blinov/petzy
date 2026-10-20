import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../src/services/api', () => ({
  default: {
    delete: vi.fn(),
    defaults: { baseURL: '/api' },
  },
}))

// React спрашивает, идёт ли проверка через act, иначе ругается на обновления вне act
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

type Deferred = typeof import('../../src/utils/deferredDelete')
type Snackbar = typeof import('../../src/utils/snackbar')
type Api = { delete: ReturnType<typeof vi.fn> }

/** Свежий модуль: состояние очереди и полосы не должно переходить из теста в тест */
async function load() {
  vi.resetModules()
  const deferred = (await import('../../src/utils/deferredDelete')) as Deferred
  const snackbar = (await import('../../src/utils/snackbar')) as Snackbar
  const api = (await import('../../src/services/api')).default as Api
  return { deferred, snackbar, api }
}

/** Что списки оставляют снаружи, с обновлением после действия */
function watchHidden(deferred: Deferred): { current: ReadonlySet<string> } {
  const box: { current: ReadonlySet<string> } = { current: new Set() }
  function Probe() {
    box.current = deferred.useHiddenRecords()
    return null
  }
  const root = createRoot(document.createElement('div'))
  act(() => {
    root.render(createElement(Probe))
  })
  return box
}

describe('deleteWithUndo', () => {
  let mod: Awaited<ReturnType<typeof load>>

  beforeEach(async () => {
    vi.useFakeTimers()
    mod = await load()
    mod.api.delete.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('запись исчезает из списка сразу', async () => {
    const box = watchHidden(mod.deferred)
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    expect(box.current.has('e1')).toBe(true)
  })

  it('до истечения времени на сервер ничего не уходит', async () => {
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    expect(mod.api.delete).not.toHaveBeenCalled()
  })

  it('по истечении времени запись удаляется на сервере', async () => {
    const onDeleted = vi.fn()
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted })
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(mod.api.delete).toHaveBeenCalledWith('/events/e1')
    expect(onDeleted).toHaveBeenCalled()
  })

  it('после удаления запись возвращается в список', async () => {
    const box = watchHidden(mod.deferred)
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(box.current.has('e1')).toBe(false)
  })

  it('отмена возвращает запись и ничего не отправляет', async () => {
    const onUndo = vi.fn()
    const box = watchHidden(mod.deferred)
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onUndo, onDeleted: () => {} })
    })
    const bar = mod.snackbar.getSnackbar()
    expect(bar?.action?.label).toBe('Отменить')
    await act(async () => {
      await mod.snackbar.runSnackbarAction(bar!.id)
    })
    expect(mod.api.delete).not.toHaveBeenCalled()
    expect(onUndo).toHaveBeenCalled()
    expect(box.current.has('e1')).toBe(false)
  })

  it('две записи ждут в одной полосе', async () => {
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Первая удалена', onDeleted: () => {} })
    })
    const firstId = mod.snackbar.getSnackbar()?.id
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e2', path: '/events/e2', message: 'Вторая удалена', onDeleted: () => {} })
    })
    expect(mod.snackbar.getSnackbar()?.id).toBe(firstId)
    expect(mod.snackbar.getSnackbar()?.message).toBe('Удалено: 2')
  })

  it('отмена возвращает обе записи', async () => {
    const onUndo = vi.fn()
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Первая удалена', onUndo, onDeleted: () => {} })
      mod.deferred.deleteWithUndo({ id: 'e2', path: '/events/e2', message: 'Вторая удалена', onUndo, onDeleted: () => {} })
    })
    const bar = mod.snackbar.getSnackbar()
    await act(async () => {
      await mod.snackbar.runSnackbarAction(bar!.id)
    })
    expect(mod.api.delete).not.toHaveBeenCalled()
    expect(onUndo).toHaveBeenCalledTimes(2)
  })

  it('если удаление не вышло, запись возвращается', async () => {
    mod.api.delete.mockRejectedValue(new Error('сервер не ответил'))
    const box = watchHidden(mod.deferred)
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(box.current.has('e1')).toBe(false)
    expect(mod.snackbar.getSnackbar()?.message).toBe('Не удалось удалить, запись возвращена')
  })

  it('чужая полоса не удаляет запись', async () => {
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    act(() => {
      mod.snackbar.showSnackbar({ message: 'Другое дело', tone: 'info' })
    })
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
    })
    expect(mod.api.delete).not.toHaveBeenCalled()
  })

  it('после чужой полосы предложение возвращается', async () => {
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    act(() => {
      mod.snackbar.showSnackbar({ message: 'Другое дело', tone: 'info' })
    })
    const other = mod.snackbar.getSnackbar()
    act(() => {
      mod.snackbar.closeSnackbar(other!.id)
    })
    await act(async () => {})
    expect(mod.snackbar.getSnackbar()?.action?.label).toBe('Отменить')
  })

  it('при закрытии вкладки отложенное удаление уходит сразу', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    act(() => {
      mod.deferred.deleteWithUndo({ id: 'e1', path: '/events/e1', message: 'Запись удалена', onDeleted: () => {} })
    })
    window.dispatchEvent(new Event('pagehide'))
    expect(fetchMock).toHaveBeenCalledWith('/api/events/e1', expect.objectContaining({ method: 'DELETE' }))
    vi.unstubAllGlobals()
  })
})
