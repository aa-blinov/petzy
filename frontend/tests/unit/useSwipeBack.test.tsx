import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { useSwipeBack } from '../../src/hooks/useSwipeBack'

/** Палец: событие с одним касанием в заданной точке */
function touch(type: string, x: number, y: number, target: EventTarget = document.body, fingers = 1) {
  const points = Array.from({ length: fingers }, () => ({ clientX: x, clientY: y }))
  const event = new TouchEvent(type, {
    touches: points as unknown as Touch[],
    changedTouches: points as unknown as Touch[],
    bubbles: true,
    cancelable: true,
  })
  target.dispatchEvent(event)
}

/** Страница, с которой можно уйти назад */
function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/', '/list']} initialIndex={1}>
      {children}
    </MemoryRouter>
  )
}

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
  vi.useRealTimers()
})

beforeEach(() => {
  // Страница в браузере и в роутере должны называться одинаково
  window.history.replaceState({ idx: 1 }, '', '/list')
})

describe('useSwipeBack', () => {
  it('свайп с левого края возвращает назад', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 10, 100)
      touch('touchend', 120, 105)
    })
    expect(result.current).toBe('/')
  })

  it('свайп, начавшийся не у края, ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 120, 100)
      touch('touchend', 220, 105)
    })
    expect(result.current).toBe('/list')
  })

  it('короткий свайп ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 10, 100)
      touch('touchend', 60, 105)
    })
    expect(result.current).toBe('/list')
  })

  it('медленный свайп ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    vi.useFakeTimers()
    act(() => {
      touch('touchstart', 10, 100)
      vi.advanceTimersByTime(400)
      touch('touchend', 120, 105)
    })
    expect(result.current).toBe('/list')
  })

  it('свайп по диагонали ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 10, 100)
      touch('touchend', 90, 150)
    })
    expect(result.current).toBe('/list')
  })

  it('два пальца ничего не делают', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 10, 100, document.body, 2)
      touch('touchend', 120, 105)
    })
    expect(result.current).toBe('/list')
  })

  it('свайп по полю ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    const input = document.createElement('input')
    document.body.appendChild(input)
    act(() => {
      touch('touchstart', 10, 100, input)
      touch('touchend', 120, 105, input)
    })
    input.remove()
    expect(result.current).toBe('/list')
  })

  it('на открытом диалоге ничего не делает', () => {
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    const dialog = document.createElement('div')
    dialog.setAttribute('role', 'dialog')
    document.body.appendChild(dialog)
    act(() => {
      touch('touchstart', 10, 100)
      touch('touchend', 120, 105)
    })
    dialog.remove()
    expect(result.current).toBe('/list')
  })

  it('когда предыдущей страницы нет, уходим на главную', () => {
    window.history.replaceState({ idx: 0 }, '', '/list')
    const { result } = renderHook(() => {
      useSwipeBack()
      return useLocation().pathname
    }, { wrapper })
    act(() => {
      touch('touchstart', 10, 100)
      touch('touchend', 120, 105)
    })
    expect(result.current).toBe('/')
  })
})
