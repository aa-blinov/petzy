import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useLocalStorage } from '../../src/hooks/useLocalStorage'

// Node держит собственное пустое хранилище и закрывает им хранилище страницы,
// поэтому берётся сначала то, что у страницы.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

const KEY = 'petzy:test:key'

afterEach(() => cleanup())

describe('useLocalStorage', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('сохранённое раньше значение читается при открытии', () => {
    window.localStorage.setItem(KEY, JSON.stringify('прежнее'))
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'начальное'))
    expect(result.current[0]).toBe('прежнее')
  })

  it('нечитаемое значение заменяется начальным', () => {
    window.localStorage.setItem(KEY, '{это не json')
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'начальное'))
    expect(result.current[0]).toBe('начальное')
  })

  it('новое значение пишется в хранилище', () => {
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'начальное'))
    act(() => result.current[1]('новое'))
    expect(window.localStorage.getItem(KEY)).toBe(JSON.stringify('новое'))
  })

  it('изменение в этой же вкладке видно второму месту', () => {
    const { result } = renderHook(() => {
      const [a, setA] = useLocalStorage<string>(KEY, 'начальное')
      const [b] = useLocalStorage<string>(KEY, 'начальное')
      return { a, b, setA }
    })
    act(() => result.current.setA('новое'))
    expect(result.current.a).toBe('новое')
    expect(result.current.b).toBe('новое')
  })

  it('изменение из другой вкладки видно здесь', () => {
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'начальное'))
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: KEY, newValue: JSON.stringify('из другой вкладки') }))
    })
    expect(result.current[0]).toBe('из другой вкладки')
  })

  it('чужой ключ не меняет значение', () => {
    const { result } = renderHook(() => useLocalStorage<string>(KEY, 'начальное'))
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', { key: 'другой', newValue: JSON.stringify('чужое') }))
    })
    expect(result.current[0]).toBe('начальное')
  })
})
