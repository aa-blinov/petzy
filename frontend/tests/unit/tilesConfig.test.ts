import { describe, expect, it } from 'vitest'
import type { EventType } from '../../src/services/eventTypes.service'
import { buildTiles, byTileOrder, isTileShown, MEDICATIONS_TILE, ORIGINAL_EVENTS } from '../../src/utils/tilesConfig'

function type(key: string, is_builtin: boolean): EventType {
  return { key, label: key, icon: 'paw', color: 'gray', is_builtin, fields: [], chart: { kind: 'count' } }
}

describe('buildTiles', () => {
  it('делает плитку на каждый тип события', () => {
    const tiles = buildTiles([type('feeding', true), type('walk', true)])
    expect(tiles.map((t) => t.id)).toEqual(['feeding', 'walk', 'medications'])
  })

  it('лекарства идут последними', () => {
    const tiles = buildTiles([type('feeding', true)])
    expect(tiles[tiles.length - 1]).toEqual(MEDICATIONS_TILE)
  })

  it('свои типы помечены как свои', () => {
    const tiles = buildTiles([type('custom_walk', false)])
    expect(tiles[0].custom).toBe(true)
  })

  it('встроенные типы своими не считаются', () => {
    const tiles = buildTiles([type('feeding', true)])
    expect(tiles[0].custom).toBe(false)
  })

  it('без типов остаётся только лекарства', () => {
    expect(buildTiles([])).toEqual([MEDICATIONS_TILE])
  })
})

describe('isTileShown', () => {
  it('изначальные восемь типов показаны', () => {
    expect(isTileShown({ order: [], visible: {} }, 'feeding')).toBe(true)
    expect(isTileShown({ order: [], visible: {} }, 'tooth_brushing')).toBe(true)
  })

  it('сказанное «скрыть» прячет плитку', () => {
    expect(isTileShown({ order: [], visible: { feeding: false } }, 'feeding')).toBe(false)
  })

  it('сказанное «показать» показывает плитку', () => {
    expect(isTileShown({ order: [], visible: { new_type: true } }, 'new_type')).toBe(true)
  })

  it('новый тип из каталога сам по себе не показан', () => {
    expect(isTileShown({ order: [], visible: {} }, 'swimming')).toBe(false)
  })

  it('свои типы показаны', () => {
    expect(isTileShown({ order: [], visible: {} }, 'custom_walk')).toBe(true)
  })

  it('лекарства показаны', () => {
    expect(isTileShown({ order: [], visible: {} }, 'medications')).toBe(true)
  })
})

describe('byTileOrder', () => {
  it('ставит плитки в выбранном порядке', () => {
    const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }]
    const sorted = byTileOrder(items, { order: ['c', 'a'], visible: {} })
    expect(sorted.map((i) => i.id)).toEqual(['c', 'a', 'b'])
  })

  it('не тронутые плитки идут после выбранных', () => {
    const items = [{ id: 'a' }, { id: 'b' }]
    const sorted = byTileOrder(items, { order: ['b'], visible: {} })
    expect(sorted.map((i) => i.id)).toEqual(['b', 'a'])
  })

  it('исходный порядок не меняется', () => {
    const items = [{ id: 'a' }, { id: 'b' }]
    byTileOrder(items, { order: ['b', 'a'], visible: {} })
    expect(items.map((i) => i.id)).toEqual(['a', 'b'])
  })

  it('без выбранного порядка остаётся порядок реестра', () => {
    const items = [{ id: 'a' }, { id: 'b' }]
    expect(byTileOrder(items, { order: [], visible: {} }).map((i) => i.id)).toEqual(['a', 'b'])
  })
})

describe('исходные восемь', () => {
  it('их ровно восемь', () => {
    expect(ORIGINAL_EVENTS).toHaveLength(8)
  })
})
