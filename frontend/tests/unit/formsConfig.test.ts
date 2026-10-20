import { describe, expect, it } from 'vitest'
import { DEFAULT_FORM_SETTINGS, isDefaultableField } from '../../src/utils/formsConfig'

describe('поля, которые помнят значение', () => {
  it('выбор, слово и число помнят значение', () => {
    expect(isDefaultableField({ type: 'select' })).toBe(true)
    expect(isDefaultableField({ type: 'text' })).toBe(true)
    expect(isDefaultableField({ type: 'number' })).toBe(true)
  })

  it('дата не помнит значение: у записи своя дата', () => {
    expect(isDefaultableField({ type: 'date' })).toBe(false)
  })

  it('время не помнит значение: у записи своё время', () => {
    expect(isDefaultableField({ type: 'time' })).toBe(false)
  })

  it('комментарий не помнит значение: его пишут каждый раз заново', () => {
    expect(isDefaultableField({ type: 'textarea' })).toBe(false)
  })

  it('без настроек новая запись начинается пустой', () => {
    expect(DEFAULT_FORM_SETTINGS).toEqual({})
  })
})
