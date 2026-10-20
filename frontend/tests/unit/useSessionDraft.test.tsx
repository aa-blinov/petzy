import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { useSessionDraft } from '../../src/hooks/useSessionDraft'
import { stashDraftsBeforeSignOut } from '../../src/utils/sessionDraft'
import { closeSnackbar, getSnackbar } from '../../src/utils/snackbar'

const KEY = 'petzy:sessionDrafts'

interface Options {
  dirty: boolean
  petId: string | null
  getValues: () => unknown
  reset: (values: unknown, options: { keepDefaultValues: boolean }) => void
  ready: boolean
  release: () => void
}

function draft() {
  const raw = window.sessionStorage.getItem(KEY)
  return raw ? (JSON.parse(raw) as Record<string, { values: unknown; petId: string | null }>) : {}
}

afterEach(() => cleanup())

describe('useSessionDraft', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
  })

  it('форма с введённым сохраняет написанное', () => {
    const options: Options = {
      dirty: true,
      petId: 'p1',
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release: vi.fn(),
    }
    renderHook(() => useSessionDraft(options))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    const saved = Object.values(draft())[0]
    expect(saved.values).toEqual({ weight: '12,4' })
    expect(saved.petId).toBe('p1')
  })

  it('чистая форма ничего не сохраняет', () => {
    const options: Options = {
      dirty: false,
      petId: 'p1',
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release: vi.fn(),
    }
    renderHook(() => useSessionDraft(options))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    expect(Object.keys(draft())).toHaveLength(0)
  })

  it('форма без питомца ничего не сохраняет', () => {
    const options: Options = {
      dirty: true,
      petId: null,
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release: vi.fn(),
    }
    renderHook(() => useSessionDraft(options))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    expect(Object.keys(draft())).toHaveLength(0)
  })

  it('когда сессия кончается, форма отпускает вопрос о несохранённом', () => {
    const release = vi.fn()
    const options: Options = {
      dirty: true,
      petId: 'p1',
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release,
    }
    renderHook(() => useSessionDraft(options))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    expect(release).toHaveBeenCalled()
  })

  it('после входа написанное возвращается в форму', async () => {
    const first: Options = {
      dirty: true,
      petId: 'p1',
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release: vi.fn(),
    }
    const { unmount } = renderHook(() => useSessionDraft(first))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    unmount()

    const reset = vi.fn()
    const second: Options = { ...first, dirty: false, reset, ready: true }
    renderHook(() => useSessionDraft(second))
    await waitFor(() => expect(reset).toHaveBeenCalledWith({ weight: '12,4' }, { keepDefaultValues: true }))
    expect(getSnackbar()?.message).toBe('Вернули то, что вы вводили до выхода')
  })

  it('написанное забирают один раз', async () => {
    const first: Options = {
      dirty: true,
      petId: 'p1',
      getValues: () => ({ weight: '12,4' }),
      reset: vi.fn(),
      ready: false,
      release: vi.fn(),
    }
    const { unmount } = renderHook(() => useSessionDraft(first))
    act(() => {
      stashDraftsBeforeSignOut()
    })
    unmount()

    const reset = vi.fn()
    const second: Options = { ...first, dirty: false, reset, ready: true }
    const { unmount: unmountSecond } = renderHook(() => useSessionDraft(second))
    await waitFor(() => expect(reset).toHaveBeenCalled())
    unmountSecond()

    const resetAgain = vi.fn()
    const third: Options = { ...first, dirty: false, reset: resetAgain, ready: true }
    renderHook(() => useSessionDraft(third))
    await act(async () => {})
    expect(resetAgain).not.toHaveBeenCalled()
  })
})
