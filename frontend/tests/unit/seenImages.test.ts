import { describe, expect, it } from 'vitest'
import { markSeen, wasSeen } from '../../src/utils/seenImages'

describe('seenImages', () => {
  it('не виденную картинку не видел', () => {
    expect(wasSeen('/files/a.png')).toBe(false)
  })

  it('после пометки картинка видна', () => {
    markSeen('/files/b.png')
    expect(wasSeen('/files/b.png')).toBe(true)
  })

  it('другая картинка не видна', () => {
    markSeen('/files/c.png')
    expect(wasSeen('/files/d.png')).toBe(false)
  })

  it('повторная пометка ничего не меняет', () => {
    markSeen('/files/e.png')
    markSeen('/files/e.png')
    expect(wasSeen('/files/e.png')).toBe(true)
  })
})
