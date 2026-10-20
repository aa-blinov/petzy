import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { setPetLookPreview, usePetLookPreview } from '../../src/utils/petLookPreview'

afterEach(() => {
  act(() => setPetLookPreview(null))
})

describe('предпросмотр вида питомца', () => {
  it('показывается всем, кто смотрит на вид питомца', () => {
    const card = renderHook(() => usePetLookPreview())
    const theme = renderHook(() => usePetLookPreview())
    act(() => setPetLookPreview({ accent: 'sage' }))
    expect(card.result.current).toEqual({ accent: 'sage' })
    expect(theme.result.current).toEqual({ accent: 'sage' })
  })

  it('второй предпросмотр заменяет первый', () => {
    const hook = renderHook(() => usePetLookPreview())
    act(() => setPetLookPreview({ accent: 'sage' }))
    act(() => setPetLookPreview({ accent: 'sky', frame: 'heart' }))
    expect(hook.result.current).toEqual({ accent: 'sky', frame: 'heart' })
  })

  it('сброс возвращает сохранённый вид', () => {
    const hook = renderHook(() => usePetLookPreview())
    act(() => setPetLookPreview({ accent: 'sage' }))
    act(() => setPetLookPreview(null))
    expect(hook.result.current).toBeNull()
  })

  it('подписчик, пришедший позже, видит текущий предпросмотр', () => {
    act(() => setPetLookPreview({ accent: 'sky' }))
    const hook = renderHook(() => usePetLookPreview())
    expect(hook.result.current).toEqual({ accent: 'sky' })
  })
})
