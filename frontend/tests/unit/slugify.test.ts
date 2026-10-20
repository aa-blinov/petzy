import { describe, expect, it } from 'vitest'
import { slugifyFieldName } from '../../src/utils/slugify'

describe('slugifyFieldName', () => {
  it('переводит кириллицу в латиницу', () => {
    expect(slugifyFieldName('Вес')).toBe('ves')
  })

  it('слова разделяет подчёркиванием', () => {
    expect(slugifyFieldName('Прогулка утром')).toBe('progulka_utrom')
  })

  it('ё читается как е', () => {
    expect(slugifyFieldName('Ёлка')).toBe('elka')
  })

  it('имя с цифры в начале получает префикс', () => {
    expect(slugifyFieldName('2 вес')).toBe('field_2_ves')
  })

  it('метка без букв получает запасное имя', () => {
    expect(slugifyFieldName('🎉')).toBe('field')
  })

  it('не повторяет уже занятое имя', () => {
    expect(slugifyFieldName('Вес', ['ves'])).toBe('ves_2')
  })

  it('ищет свободное имя дальше, если занято и следующее', () => {
    expect(slugifyFieldName('Вес', ['ves', 'ves_2'])).toBe('ves_3')
  })

  it('не трогает свободное имя', () => {
    expect(slugifyFieldName('Вес', ['ves_2'])).toBe('ves')
  })

  it('имя не длиннее пятидесяти знаков', () => {
    expect(slugifyFieldName('а'.repeat(60))).toHaveLength(50)
  })

  it('имя из пятидесяти знаков остаётся целым', () => {
    expect(slugifyFieldName('а'.repeat(50))).toBe('a'.repeat(50))
  })

  it('имя начинается с буквы', () => {
    expect(slugifyFieldName('1')).toMatch(/^[a-z]/)
  })
})

describe('slugifyFieldName при занятом имени', () => {
  it('имя в пятьдесят знаков всё равно находит свободное', () => {
    // Раньше суффикс срезался по длине, имя оставалось прежним, и цикл не кончался: вкладка зависала.
    const long = 'a'.repeat(50)
    const free = slugifyFieldName(long, [long])
    expect(free).not.toBe(long)
    expect(free).toMatch(/^[a-z][a-z0-9_]{0,49}$/)
    expect(free.length).toBeLessThanOrEqual(50)
  })

  it('имя в пятьдесят знаков находит и третье свободное', () => {
    const long = 'a'.repeat(50)
    const second = slugifyFieldName(long, [long])
    const third = slugifyFieldName(long, [long, second])
    expect(third).not.toBe(long)
    expect(third).not.toBe(second)
    expect(third).toMatch(/^[a-z][a-z0-9_]{0,49}$/)
  })
})
