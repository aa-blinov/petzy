import { describe, expect, it } from 'vitest'
import { uniqueById } from '../../src/utils/uniqueById'

describe('uniqueById', () => {
  it('оставляет первую запись каждого id', () => {
    const items = [
      { _id: 'a', n: 1 },
      { _id: 'b', n: 2 },
      { _id: 'a', n: 3 },
    ]
    expect(uniqueById(items)).toEqual([
      { _id: 'a', n: 1 },
      { _id: 'b', n: 2 },
    ])
  })

  it('не переставляет записи, которые остались', () => {
    const items = [{ _id: 'a' }, { _id: 'b' }, { _id: 'c' }]
    expect(uniqueById(items).map((i) => i._id)).toEqual(['a', 'b', 'c'])
  })

  it('пустой список остаётся пустым', () => {
    expect(uniqueById([])).toEqual([])
  })

  it('не меняет исходный список', () => {
    const items = [{ _id: 'a' }, { _id: 'a' }]
    uniqueById(items)
    expect(items).toHaveLength(2)
  })
})
