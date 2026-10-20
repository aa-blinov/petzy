import { describe, expect, it } from 'vitest'
import { catalogSpecies, inferProtects } from '../../src/hooks/useVaccineCatalog'
import type { VaccineCatalog } from '../../src/services/vaccines.service'

const catalog: VaccineCatalog = {
  groups: [],
  products: [
    { name: 'Нобивак DHP', species: ['dog'], protects: 'Чума, гепатит, парвовирус' },
    { name: 'Нобивак DHPPi', species: ['dog'], protects: 'Чума, гепатит, парвовирус, лептоспироз' },
    { name: 'Комплексная прививка', species: ['dog'], protects: 'Много' },
    { name: 'Рабивин', species: ['dog'], protects: 'Бешенство' },
    { name: 'Рабивин Н', species: ['dog'], protects: 'Бешенство, лептоспироз' },
    { name: 'Вакцина для кошек', species: ['cat'], protects: 'Панлейкопения' },
  ],
}

describe('catalogSpecies', () => {
  it('собака, кошка и кролик сохраняют свой вид', () => {
    expect(catalogSpecies('dog')).toBe('dog')
    expect(catalogSpecies('cat')).toBe('cat')
    expect(catalogSpecies('rabbit')).toBe('rabbit')
  })

  it('питомец вида, для которого нет списка, получает общий список', () => {
    expect(catalogSpecies('hamster')).toBe('other')
    expect(catalogSpecies(undefined)).toBe('other')
  })
})

describe('inferProtects', () => {
  it('без каталога прививка не узнаётся', () => {
    expect(inferProtects('Нобивак DHP', undefined, 'dog')).toBeNull()
  })

  it('точное название вакцины узнаётся', () => {
    expect(inferProtects('Нобивак DHP', catalog, 'dog')).toBe('Чума, гепатит, парвовирус')
  })

  it('название с годом в конце узнаётся', () => {
    expect(inferProtects('Нобивак DHPPi (2025)', catalog, 'dog')).toBe('Чума, гепатит, парвовирус, лептоспироз')
  })

  it('самое длинное известное название выигрывает', () => {
    expect(inferProtects('Рабивин Н', catalog, 'dog')).toBe('Бешенство, лептоспироз')
  })

  it('комплексная прививка не узнаётся', () => {
    expect(inferProtects('Комплексная прививка', catalog, 'dog')).toBeNull()
  })

  it('вакцина другого вида не подходит', () => {
    expect(inferProtects('Вакцина для кошек', catalog, 'dog')).toBeNull()
  })

  it('пустое название не узнаётся', () => {
    expect(inferProtects('   ', catalog, 'dog')).toBeNull()
  })
})
