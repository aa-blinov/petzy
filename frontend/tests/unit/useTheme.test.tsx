import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, renderHook } from '@testing-library/react'
import { useTheme } from '../../src/hooks/useTheme'

afterEach(() => cleanup())

describe('useTheme', () => {
  it('без провайдера темы хук объясняет, что его забыли', () => {
    expect(() => renderHook(() => useTheme())).toThrow('useTheme must be used within a ThemeProvider')
  })
})
