import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useFabAway } from '../../src/hooks/useFabAway'

/** Прокрутка страницы: браузер отдаёт её в scrollY, а страница узнаёт о движении по событию */
function scrollTo(y: number) {
  Object.defineProperty(window, 'scrollY', { value: y, configurable: true, writable: true })
  window.dispatchEvent(new Event('scroll'))
}

afterEach(() => {
  cleanup()
  Object.defineProperty(window, 'scrollY', { value: 0, configurable: true, writable: true })
})

describe('useFabAway', () => {
  it('прокрутка вниз убирает кнопку', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(200))
    expect(result.current).toBe(true)
  })

  it('маленькая прокрутка вверх кнопку не возвращает', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(200))
    act(() => scrollTo(195))
    expect(result.current).toBe(true)
  })

  it('маленькая прокрутка вниз кнопку не убирает', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(200))
    act(() => scrollTo(190))
    act(() => scrollTo(195))
    expect(result.current).toBe(false)
  })

  it('прокрутка вверх возвращает кнопку', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(200))
    act(() => scrollTo(190))
    expect(result.current).toBe(false)
  })

  it('у верха страницы кнопка остаётся на месте', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(50))
    expect(result.current).toBe(false)
  })

  it('нажатие клавиши возвращает кнопку', () => {
    const { result } = renderHook(() => useFabAway())
    act(() => scrollTo(200))
    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    })
    expect(result.current).toBe(false)
  })
})
