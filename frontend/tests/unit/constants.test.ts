import { describe, expect, it } from 'vitest'
import { genderLabel, pastelColorMap, TILE_COLORS, TILE_COLOR_LABELS } from '../../src/utils/constants'

describe('genderLabel', () => {
  it('код мужского читается по-русски', () => {
    expect(genderLabel('male')).toBe('Мальчик')
  })

  it('код женского читается по-русски', () => {
    expect(genderLabel('female')).toBe('Девочка')
  })

  it('старые значения читаются как новые', () => {
    expect(genderLabel('Мужской')).toBe('Мальчик')
    expect(genderLabel('Женский')).toBe('Девочка')
  })

  it('пустого пола нет', () => {
    expect(genderLabel('')).toBe('')
    expect(genderLabel(null)).toBe('')
    expect(genderLabel(undefined)).toBe('')
  })

  it('незнакомое значение показывают как есть', () => {
    expect(genderLabel('Другое')).toBe('Другое')
  })
})

describe('цвета плиток', () => {
  it('у каждого цвета есть название', () => {
    for (const color of Object.keys(TILE_COLORS)) {
      expect(TILE_COLOR_LABELS[color as keyof typeof TILE_COLOR_LABELS]).toBeTruthy()
    }
  })

  it('у каждого цвета есть свой оттенок', () => {
    for (const color of Object.keys(TILE_COLORS)) {
      expect(pastelColorMap[color]).toBeTruthy()
    }
  })

  it('названия цветов без латиницы', () => {
    for (const label of Object.values(TILE_COLOR_LABELS)) {
      expect(label).toMatch(/^[А-Яа-яЁё]+$/)
    }
  })
})
