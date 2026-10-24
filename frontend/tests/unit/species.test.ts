import { describe, expect, it } from 'vitest'
import { defaultTilesFor, getSpecies, MORE_SPECIES, neuteringLabel, SPECIES, speciesLabel, suggestedFirst, TILE_SPECIES } from '../../src/utils/species'

describe('getSpecies', () => {
  it('по ключу находит вид', () => {
    expect(getSpecies('cat').key).toBe('cat')
  })

  it('по названию находит вид', () => {
    expect(getSpecies('Кот').key).toBe('cat')
  })

  it('по названию с пробелами находит вид', () => {
    expect(getSpecies('  кот  ').key).toBe('cat')
  })

  it('по слову из прежних записей находит вид', () => {
    expect(getSpecies('кошка').key).toBe('cat')
    expect(getSpecies('собака').key).toBe('dog')
    expect(getSpecies('попугай').key).toBe('bird')
    expect(getSpecies('ящерица').key).toBe('reptile')
  })

  it('незнакомое значение становится «Другой питомец»', () => {
    expect(getSpecies('дракон').key).toBe('other')
  })

  it('пустое значение становится «Другой питомец»', () => {
    expect(getSpecies('').key).toBe('other')
    expect(getSpecies(null).key).toBe('other')
    expect(getSpecies(undefined).key).toBe('other')
  })
})

describe('speciesLabel', () => {
  it('по ключу показывает название', () => {
    expect(speciesLabel('cat')).toBe('Кот')
  })

  it('свободный текст показывают как есть', () => {
    expect(speciesLabel('Ёжик')).toBe('Ёжик')
  })

  it('пустого вида нет', () => {
    expect(speciesLabel('')).toBe('')
    expect(speciesLabel(null)).toBe('')
  })
})

describe('neuteringLabel', () => {
  it('для самца кастрация', () => {
    expect(neuteringLabel('male')).toBe('Кастрация')
    expect(neuteringLabel('Мужской')).toBe('Кастрация')
  })

  it('для самки стерилизация', () => {
    expect(neuteringLabel('female')).toBe('Стерилизация')
    expect(neuteringLabel('Женский')).toBe('Стерилизация')
  })

  it('без пола оба слова', () => {
    expect(neuteringLabel(null)).toBe('Кастрация или стерилизация')
    expect(neuteringLabel('')).toBe('Кастрация или стерилизация')
  })
})

describe('defaultTilesFor', () => {
  it('плитки идут в порядке набора для вида', () => {
    expect(defaultTilesFor('cat').order).toEqual(['feeding', 'weight', 'litter', 'vomiting', 'brushing'])
  })

  it('плитки набора показаны', () => {
    const visible = defaultTilesFor('cat').visible
    expect(visible.feeding).toBe(true)
    expect(visible.vomiting).toBe(true)
  })

  it('изначальные восемь, не вошедшие в набор, скрыты', () => {
    const visible = defaultTilesFor('cat').visible
    expect(visible.asthma).toBe(false)
    expect(visible.eye_drops).toBe(false)
  })

  it('у рыбки веса на плитке нет', () => {
    expect(defaultTilesFor('fish').visible.weight).toBe(false)
  })

  it('незнакомый вид получает набор «Другой питомец»', () => {
    expect(defaultTilesFor('дракон').order).toEqual(defaultTilesFor('other').order)
  })
})

describe('список видов', () => {
  it('плитку получают пять видов', () => {
    expect(TILE_SPECIES).toEqual(['cat', 'dog', 'rabbit', 'bird', 'fish'])
  })

  it('остальные виды попадают в «Другой»', () => {
    expect(MORE_SPECIES).toHaveLength(SPECIES.length - TILE_SPECIES.length)
  })

  it('в «Другой» нет видов с плиткой', () => {
    for (const { value } of MORE_SPECIES) {
      expect(TILE_SPECIES).not.toContain(value)
    }
  })

  it('у каждого вида есть свои названия и иконка', () => {
    for (const species of SPECIES) {
      expect(species.label).toBeTruthy()
      expect(species.forWhom).toBeTruthy()
      expect(species.question).toBeTruthy()
      expect(species.icon).toBeTruthy()
      expect(species.events.length).toBeGreaterThan(0)
    }
  })

  it('у каждого вида ключ встречается один раз', () => {
    const keys = SPECIES.map((s) => s.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('стерилизация есть только у млекопитающих', () => {
    expect(getSpecies('bird').neutering).toBe(false)
    expect(getSpecies('fish').neutering).toBe(false)
    expect(getSpecies('turtle').neutering).toBe(false)
    expect(getSpecies('cat').neutering).toBe(true)
  })
})

describe('suggestedFirst', () => {
  const tiles = [{ id: 'uv_lamp' }, { id: 'brushing' }, { id: 'misting' }, { id: 'litter' }, { id: 'play' }];

  it('puts what the species suggests first, in its own order, and keeps the rest as they were', () => {
    expect(suggestedFirst(tiles, ['litter', 'brushing']).map((t) => t.id)).toEqual(['litter', 'brushing', 'uv_lamp', 'misting', 'play']);
  })

  it('hides nothing and does not change the list it is given', () => {
    const copy = [...tiles]
    expect(suggestedFirst(tiles, ['play'])).toHaveLength(tiles.length)
    expect(tiles).toEqual(copy)
  })

  it('leaves the order alone when nothing is suggested', () => {
    expect(suggestedFirst(tiles, []).map((t) => t.id)).toEqual(tiles.map((t) => t.id))
  })
})
