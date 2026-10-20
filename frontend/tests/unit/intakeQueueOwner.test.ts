import { describe, expect, it } from 'vitest'
import { claimUnowned, queueOf, type OwnedEntry } from '../../src/utils/intakeQueueOwner'

const entry = (owner?: string): OwnedEntry => ({ owner })

describe('queueOf', () => {
  it('без входа очередь пуста: отметки не показываются никому', () => {
    expect(queueOf([entry('alice'), entry('bob'), entry()], null)).toEqual([])
  })

  it('своя отметка видна своему логину', () => {
    expect(queueOf([entry('alice'), entry('bob')], 'alice')).toEqual([{ owner: 'alice' }])
  })

  it('чужая отметка не видна: телефон могут отдать другому', () => {
    const visible = queueOf([entry('bob')], 'alice')
    expect(visible).toEqual([])
  })

  it('отметка без владельца видна тому, кто войдёт', () => {
    const visible = queueOf([entry(), entry('bob')], 'alice')
    expect(visible).toHaveLength(1)
    expect(visible[0].owner).toBeUndefined()
  })
})

describe('claimUnowned', () => {
  it('отметка без владельца достаётся тому, кто её отправил', () => {
    const claimed = claimUnowned([entry('bob'), entry()], 'alice')
    expect(claimed[0].owner).toBe('bob')
    expect(claimed[1].owner).toBe('alice')
  })

  it('чужая отметка не переписывается на другого', () => {
    const claimed = claimUnowned([entry('bob')], 'alice')
    expect(claimed[0].owner).toBe('bob')
  })

  it('когда незабирать нечего, массив остаётся тот же', () => {
    const items = [entry('alice')]
    expect(claimUnowned(items, 'alice')).toBe(items)
  })

  it('когда есть что забрать, возвращается новый массив', () => {
    const items = [entry('alice'), entry()]
    expect(claimUnowned(items, 'alice')).not.toBe(items)
  })
})
