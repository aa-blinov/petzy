import { describe, expect, it } from 'vitest'
import type { MedicalProfile } from '../../src/services/medicalCard.service'
import { formatDate, hasLife, petIdentity, weightDelta } from '../../src/utils/medicalCardFormat'

/** Профиль с заполненными полями: незаполненные в нём пустые. */
const profile = (fields: Partial<MedicalProfile>) => fields as MedicalProfile

describe('дата на медкарте', () => {
  it('записана так, как её пишет человек: 04.10.2026', () => {
    expect(formatDate('2026-10-04')).toBe('04.10.2026')
  })

  it('время в дате не сдвигает день', () => {
    expect(formatDate('2026-10-04T23:30:00Z')).toBe('04.10.2026')
  })
})

describe('профиль питомца', () => {
  it('заполнен, если сказано хоть что-то о питании или жизни', () => {
    expect(hasLife(profile({ diet: 'сухой корм' }))).toBe(true)
    expect(hasLife(profile({ living: 'квартира' }))).toBe(true)
    expect(hasLife(profile({ reproduction: 'родила' }))).toBe(true)
  })

  it('пустой профиль не выглядит заполненным', () => {
    expect(hasLife(profile({}))).toBe(false)
  })

  it('пустая строка не считается заполненной', () => {
    expect(hasLife(profile({ diet: '', living: '', reproduction: '' }))).toBe(false)
  })
})

describe('изменение веса', () => {
  it('без взвешиваний изменений нет', () => {
    expect(weightDelta([])).toBeNull()
  })

  it('с одним взвешиванием сравнивать не с чем', () => {
    expect(weightDelta([{ date: '2026-10-01', value: 5 }])).toBeNull()
  })

  it('вес не изменился: пишем дату прошлого взвешивания', () => {
    expect(weightDelta([
      { date: '2026-10-01', value: 5 },
      { date: '2026-10-04', value: 5 },
    ])).toBe('Без изменений с 01.10.2026')
  })

  it('вес вырос: пишем, на сколько и с какой даты', () => {
    expect(weightDelta([
      { date: '2026-10-01', value: 5 },
      { date: '2026-10-04', value: 5.4 },
    ])).toBe('+0,4 кг с 01.10.2026')
  })

  it('вес упал: перед числом минус, а не дефис', () => {
    const delta = weightDelta([
      { date: '2026-10-01', value: 5.4 },
      { date: '2026-10-04', value: 5 },
    ])
    expect(delta).toBe('−0,4 кг с 01.10.2026')
    expect(delta).not.toContain('-')
  })

  it('разница округляется до двух знаков', () => {
    expect(weightDelta([
      { date: '2026-10-01', value: 10 },
      { date: '2026-10-04', value: 10.05 },
    ])).toBe('+0,05 кг с 01.10.2026')
  })

  it('сравниваются два последних взвешивания, а не первые', () => {
    expect(weightDelta([
      { date: '2026-09-01', value: 4 },
      { date: '2026-10-01', value: 5 },
      { date: '2026-10-04', value: 5 },
    ])).toBe('Без изменений с 01.10.2026')
  })
})

describe("кто питомец на медкарте", () => {
  it("вид открывает строку с заглавной, даже если записан строчными", () => {
    expect(petIdentity({ species: "собака", breed: "Лабрадор" })).toBe("Собака, лабрадор")
  })

  it("без вида строка начинается с породы с заглавной", () => {
    expect(petIdentity({ species: null, breed: "лабрадор" })).toBe("Лабрадор")
  })

  it("пустая строка остаётся пустой", () => {
    expect(petIdentity({})).toBe("")
  })
})
