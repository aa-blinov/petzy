import { describe, expect, it } from 'vitest'
import { clinicNames, distinctNames, doctorNames, type PlaceSources } from '../../src/utils/placeOptions'

const base: PlaceSources = {
  profileClinics: [{ name: 'Айболит', doctors: [{ name: 'Иванова И.И.' }] }],
  records: [],
  knownClinics: [],
  knownDoctors: [],
}

describe('клиники и врачи для выбора в форме записи', () => {
  it('клиника из записи, которой нет среди последних десяти, предлагается через известные места', () => {
    const names = clinicNames({ ...base, knownClinics: ['Лапка', 'Старая клиника'] })
    expect(names).toEqual(['Айболит', 'Лапка', 'Старая клиника'])
  })

  it('регистр и пробелы по краям не делают вторую клинику', () => {
    expect(clinicNames({ ...base, records: [{ clinic: ' айболит ' }], knownClinics: ['АЙБОЛИТ'] })).toEqual(['Айболит'])
  })

  it('выбранное сейчас значение не теряется, если его нет нигде', () => {
    expect(clinicNames({ ...base, clinicValue: 'Вет-Дом' })).toEqual(['Айболит', 'Вет-Дом'])
    expect(distinctNames([], 'X')).toEqual(['X'])
  })

  it('без выбранной клиники врачи всех клиник и известные по другим питомцам', () => {
    const names = doctorNames({ ...base, knownDoctors: [{ name: 'Петров П.П.', clinic: 'Лапка' }] })
    expect(names).toEqual(['Иванова И.И.', 'Петров П.П.'])
  })

  it('с выбранной клиникой профиля только её врачи и те, кого видели в ней', () => {
    const names = doctorNames({
      ...base,
      clinicValue: 'Айболит',
      knownDoctors: [
        { name: 'Петров П.П.', clinic: 'Лапка' },
        { name: 'Сидорова С.С.', clinic: 'Айболит' },
        { name: 'Без клиники', clinic: null },
      ],
    })
    expect(names).toEqual(['Иванова И.И.', 'Сидорова С.С.', 'Без клиники'])
  })

  it('с одноразовой клиникой, которой нет в профиле, врачи, виденные в ней', () => {
    const names = doctorNames({
      ...base,
      clinicValue: 'Вет-Дом',
      knownDoctors: [
        { name: 'Орлов О.О.', clinic: 'Вет-Дом' },
        { name: 'Петров П.П.', clinic: 'Лапка' },
      ],
    })
    expect(names).toEqual(['Орлов О.О.'])
  })
})
