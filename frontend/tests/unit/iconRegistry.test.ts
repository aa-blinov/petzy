import { describe, expect, it } from 'vitest'
import { FALLBACK_ICON, getEventIcon, ICON_LABELS, ICON_OPTIONS, ICON_REGISTRY } from '../../src/utils/iconRegistry'

describe('getEventIcon', () => {
  it('отдаёт иконку по ключу', () => {
    expect(getEventIcon('eye')).toBe(ICON_REGISTRY.eye)
  })

  it('незнакомый ключ получает запасную иконку', () => {
    expect(getEventIcon('нет-такой')).toBe(FALLBACK_ICON)
  })

  it('пустой ключ получает запасную иконку', () => {
    expect(getEventIcon('')).toBe(FALLBACK_ICON)
  })
})

describe('реестр иконок', () => {
  it('у каждой иконки есть название', () => {
    for (const key of Object.keys(ICON_REGISTRY)) {
      expect(ICON_LABELS[key]).toBeTruthy()
    }
  })

  it('названия иконок без латиницы', () => {
    for (const label of Object.values(ICON_LABELS)) {
      expect(label).toMatch(/^[А-Яа-яЁё ]+$/)
    }
  })
})

describe('ICON_OPTIONS', () => {
  it('в списке каждая иконка реестра', () => {
    expect(ICON_OPTIONS.map((o) => o.key)).toEqual(Object.keys(ICON_REGISTRY))
  })

  it('у каждого пункта есть иконка и название', () => {
    for (const option of ICON_OPTIONS) {
      expect(option.Icon).toBeTruthy()
      expect(option.label).toBeTruthy()
    }
  })
})
