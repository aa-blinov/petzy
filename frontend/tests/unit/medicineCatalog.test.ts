import { describe, expect, it } from 'vitest'
import { parasiteTargetOf } from '../../src/utils/medicalSuggestions'
import { MEDICINE_GROUPS } from '../../src/utils/medicineCatalog'

describe('каталог лекарств', () => {
  it('у каждой группы есть название и лекарства', () => {
    for (const group of MEDICINE_GROUPS) {
      expect(group.label).toBeTruthy()
      expect(group.items.length).toBeGreaterThan(0)
    }
  })

  it('ключи групп не повторяются', () => {
    const keys = MEDICINE_GROUPS.map((g) => g.key)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('лекарство не стоит в двух группах сразу', () => {
    const names = MEDICINE_GROUPS.flatMap((g) => g.items)
    expect(new Set(names).size).toBe(names.length)
  })

  it('в группе от паразитов только те, чью цель форма знает', () => {
    const group = MEDICINE_GROUPS.find((g) => g.key === 'parasites')
    expect(group).toBeTruthy()
    for (const name of group!.items) {
      expect(parasiteTargetOf(name)).toBeTruthy()
    }
  })
})
