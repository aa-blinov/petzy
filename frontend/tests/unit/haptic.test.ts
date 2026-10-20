import { afterEach, describe, expect, it } from 'vitest'
import { hapticFeedback } from '../../src/utils/haptic'

afterEach(() => {
  Reflect.deleteProperty(navigator, 'vibrate')
})

describe('отклик на нажатие', () => {
  it('на компьютере без вибрации ничего не ломается', () => {
    expect(() => hapticFeedback()).not.toThrow()
  })

  it('сильный отклик длиннее слабого', () => {
    const patterns: number[] = []
    Object.defineProperty(navigator, 'vibrate', {
      value: (pattern: number) => {
        patterns.push(pattern)
        return true
      },
      configurable: true,
    })
    hapticFeedback('light')
    hapticFeedback('medium')
    hapticFeedback('heavy')
    expect(patterns.length).toBe(3)
    expect(patterns[0]).toBeLessThan(patterns[1])
    expect(patterns[1]).toBeLessThan(patterns[2])
  })
})
