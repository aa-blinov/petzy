import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useTouched } from '../../src/hooks/useTouched'

afterEach(() => cleanup())

describe('useTouched', () => {
  it('пока поле не оставлено, ошибка не видна', () => {
    const { result } = renderHook(() => useTouched(false))
    expect(result.current.shows('вес')).toBe(false)
  })

  it('после того как поле оставлено, его ошибка видна', () => {
    const { result } = renderHook(() => useTouched(false))
    act(() => {
      result.current.touch('вес')()
    })
    expect(result.current.shows('вес')).toBe(true)
  })

  it('оставленное поле не открывает ошибки других полей', () => {
    const { result } = renderHook(() => useTouched(false))
    act(() => {
      result.current.touch('вес')()
    })
    expect(result.current.shows('имя')).toBe(false)
  })

  it('после отправки видны ошибки всех полей', () => {
    const { result } = renderHook(() => useTouched(true))
    expect(result.current.shows('вес')).toBe(true)
    expect(result.current.shows('имя')).toBe(true)
  })
})
