import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useSwipeableRow } from '../../src/hooks/useSwipeableRow'
import type { PointerEvent as ReactPointerEvent, MouseEvent as ReactMouseEvent } from 'react'

/** Палец или мышь: событие с точкой */
function pointer(x: number, y: number) {
  return {
    isPrimary: true,
    pointerType: 'touch',
    button: 0,
    clientX: x,
    clientY: y,
    pointerId: 1,
    currentTarget: { setPointerCapture: vi.fn(), releasePointerCapture: vi.fn() },
    preventDefault: vi.fn(),
  } as unknown as ReactPointerEvent
}

/** Клик, который ряд может проглотить */
function click() {
  return { stopPropagation: vi.fn(), preventDefault: vi.fn() } as unknown as ReactMouseEvent
}

afterEach(() => cleanup())

beforeEach(() => {
  vi.useFakeTimers()
})

describe('useSwipeableRow', () => {
  it('короткий свайп возвращает ряд на место', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(120, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(120, 100))
    })
    expect(result.current.offset).toBe(0)
    expect(onSwipeRight).not.toHaveBeenCalled()
  })

  it('отменённый браузером жест не вызывает действие', () => {
    // The browser took the gesture away (it started scrolling). Such a gesture is not a
    // swipe, and it must not delete the row.
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(200, 100))
    })
    act(() => {
      result.current.handlers.onPointerCancel?.(pointer(200, 100))
    })
    expect(onSwipeRight).not.toHaveBeenCalled()
    expect(result.current.offset).toBe(0)
  })

  it('свайп дальше порога вызывает действие', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(160, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(160, 100))
    })
    expect(onSwipeRight).toHaveBeenCalled()
  })

  it('свайп в сорок пикселей считается свайпом', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(140, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(140, 100))
    })
    expect(onSwipeRight).toHaveBeenCalled()
  })

  it('свайп в тридцать девять пикселей не считается свайпом', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      vi.advanceTimersByTime(500)
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(139, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(139, 100))
    })
    expect(onSwipeRight).not.toHaveBeenCalled()
  })

  it('быстрый рывок считается свайпом', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(120, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(120, 100))
    })
    expect(onSwipeRight).toHaveBeenCalled()
  })

  it('действие вызывается с той стороны, где ряд остановился', () => {
    const onSwipeLeft = vi.fn()
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeLeft, onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(160, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(60, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(60, 100))
    })
    expect(onSwipeLeft).toHaveBeenCalled()
    expect(onSwipeRight).not.toHaveBeenCalled()
  })

  it('вертикальное движение ряд не двигает', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(105, 140))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(105, 140))
    })
    expect(result.current.offset).toBe(0)
    expect(onSwipeRight).not.toHaveBeenCalled()
  })

  it('выключенный ряд не двигается', () => {
    const onSwipeRight = vi.fn()
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight, disabled: true }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(160, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(160, 100))
    })
    expect(result.current.offset).toBe(0)
    expect(onSwipeRight).not.toHaveBeenCalled()
  })

  it('после действия ряд сам возвращается на место', () => {
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight: vi.fn() }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(160, 100))
    })
    act(() => {
      result.current.handlers.onPointerUp(pointer(160, 100))
    })
    expect(result.current.offset).not.toBe(0)
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current.offset).toBe(0)
  })

  it('клик после свайпа не доходит до ряда', () => {
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight: vi.fn() }))
    act(() => {
      result.current.handlers.onPointerDown(pointer(100, 100))
    })
    act(() => {
      result.current.handlers.onPointerMove(pointer(160, 100))
    })
    const event = click()
    act(() => {
      result.current.handlers.onClickCapture(event)
    })
    expect(event.stopPropagation).toHaveBeenCalled()
  })

  it('клик без свайпа доходит до ряда', () => {
    const { result } = renderHook(() => useSwipeableRow({ onSwipeRight: vi.fn() }))
    const event = click()
    act(() => {
      result.current.handlers.onClickCapture(event)
    })
    expect(event.stopPropagation).not.toHaveBeenCalled()
  })
})
