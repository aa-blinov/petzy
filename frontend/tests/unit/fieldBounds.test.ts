import { describe, expect, it } from 'vitest'
import { hardBounds, shown } from '../../src/utils/fieldBounds'

describe('hardBounds', () => {
  it('ограничивает вес снизу и сверху', () => {
    expect(hardBounds('weight', 'weight')).toEqual([0.01, 100])
  })

  it('ограничивает вес корма', () => {
    expect(hardBounds('feeding', 'food_weight')).toEqual([0.1, 5000])
  })

  it('для неизвестного типа поля нет', () => {
    expect(hardBounds('walk', 'weight')).toBeNull()
  })

  it('для известного типа, но чужого поля нет', () => {
    expect(hardBounds('weight', 'food_weight')).toBeNull()
  })

  it('без типа поля нет', () => {
    expect(hardBounds(undefined, 'weight')).toBeNull()
  })
})

describe('shown', () => {
  it('показывает дробь с запятой', () => {
    expect(shown(0.01)).toBe('0,01')
  })

  it('разделяет тысячи неразрывным пробелом', () => {
    expect(shown(5000)).toBe('5\u00A0000')
  })

  it('целое число без разделителей', () => {
    expect(shown(100)).toBe('100')
  })
})
