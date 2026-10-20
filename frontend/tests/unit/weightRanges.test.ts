import { describe, expect, it } from 'vitest'
import { weightRangeByYear } from '../../src/utils/weightRanges'

describe('weightRangeByYear', () => {
  it('без замеров строка пустая', () => {
    expect(weightRangeByYear([])).toBe('')
  })

  it('годы идут по порядку, в каждом от меньшего к большему', () => {
    const line = weightRangeByYear([
      { date: '2026-01-05', value: 8.8 },
      { date: '2025-07-01', value: 9.1 },
      { date: '2025-03-01', value: 8.2 },
    ])
    expect(line).toBe('2025: от 8,2 до 9,1 кг, 2026: 8,8 кг')
  })

  it('один замер в году даёт одно число', () => {
    expect(weightRangeByYear([{ date: '2025-03-01', value: 8.2 }])).toBe('2025: 8,2 кг')
  })
})
