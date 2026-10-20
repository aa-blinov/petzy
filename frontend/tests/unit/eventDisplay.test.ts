import { describe, expect, it } from 'vitest'
import type { EventType, EventTypeField } from '../../src/services/eventTypes.service'
import { buildEventDisplayConfig, buildEventDisplayConfigs, eventDetails, MEDICATIONS_DISPLAY, type HistoryItem } from '../../src/utils/eventDisplay'

const field = (fields: Partial<EventTypeField> & { name: string; label: string }): EventTypeField => ({
  type: 'text',
  required: false,
  ...fields,
})

const eventType = (fields: EventTypeField[]): EventType => ({
  key: 'food',
  label: 'Кормление',
  icon: 'utensils',
  color: 'orange',
  is_builtin: true,
  fields,
  chart: { kind: 'count' },
})

const item = (fields: Record<string, unknown>): HistoryItem => ({
  _id: 'e1',
  date_time: '2026-10-20 08:00',
  fields,
})

describe('MEDICATIONS_DISPLAY', () => {
  it('лекарство и доза стоят рядом с единицей', () => {
    const lines = MEDICATIONS_DISPLAY.details({
      _id: 'e1',
      date_time: '2026-10-20 08:00',
      medication_name: 'Синулокс',
      dose_taken: 0.5,
      dose_unit: 'таб',
    })
    expect(lines).toEqual([
      { label: 'Лекарство', value: 'Синулокс' },
      { label: 'Доза', value: '0,5 таб' },
    ])
  })

  it('пропущенный приём говорит, что ничего не дали', () => {
    const lines = MEDICATIONS_DISPLAY.details({
      _id: 'e1',
      date_time: '2026-10-20 08:00',
      medication_name: 'Синулокс',
      dose_taken: 1,
      skipped: true,
    })
    expect(lines[1]).toEqual({ label: 'Приём', value: 'пропущен' })
  })

  it('лекарство без названия называется неизвестным', () => {
    const lines = MEDICATIONS_DISPLAY.details({ _id: 'e1', date_time: '2026-10-20 08:00', dose_taken: 1 })
    expect(lines[0]).toEqual({ label: 'Лекарство', value: 'Неизвестно' })
  })

  it('комментарий идёт отдельной строкой', () => {
    const lines = MEDICATIONS_DISPLAY.details({
      _id: 'e1',
      date_time: '2026-10-20 08:00',
      medication_name: 'Синулокс',
      dose_taken: 1,
      comment: 'с ложки',
    })
    expect(lines[lines.length - 1]).toEqual({ label: 'Комментарий', value: 'с ложки' })
  })

  it('прочерк не считается комментарием', () => {
    const lines = MEDICATIONS_DISPLAY.details({
      _id: 'e1',
      date_time: '2026-10-20 08:00',
      medication_name: 'Синулокс',
      dose_taken: 1,
      comment: '-',
    })
    expect(lines).toHaveLength(2)
  })
})

describe('eventDetails', () => {
  it('поля идут в порядке объявления типа', () => {
    const lines = eventDetails(item({ weight: 60, kind: 'сухой' }), eventType([
      field({ name: 'kind', label: 'Корм' }),
      field({ name: 'weight', label: 'Вес', type: 'number' }),
    ]))
    expect(lines.map((line) => line.label)).toEqual(['Корм', 'Вес'])
  })

  it('выбор показывает текст, а не сохранённое значение', () => {
    const lines = eventDetails(item({ kind: 'dry' }), eventType([
      field({
        name: 'kind',
        label: 'Корм',
        type: 'select',
        options: [
          { value: 'dry', text: 'сухой' },
          { value: 'wet', text: 'влажный' },
        ],
      }),
    ]))
    expect(lines[0]).toEqual({ label: 'Корм', value: 'сухой' })
  })

  it('пустое поле пропускается', () => {
    const lines = eventDetails(item({ kind: '' }), eventType([field({ name: 'kind', label: 'Корм' })]))
    expect(lines).toEqual([])
  })

  it('единица из подписи переезжает к числу', () => {
    const lines = eventDetails(item({ weight: 60 }), eventType([
      field({ name: 'weight', label: 'Вес корма (г)', type: 'number' }),
    ]))
    expect(lines[0]).toEqual({ label: 'Вес корма', value: '60 г' })
  })

  it('у текстового поля подпись не трогается', () => {
    const lines = eventDetails(item({ kind: 'Вес корма (г)' }), eventType([
      field({ name: 'kind', label: 'Вес корма (г)' }),
    ]))
    expect(lines[0]).toEqual({ label: 'Вес корма (г)', value: 'Вес корма (г)' })
  })
})

describe('buildEventDisplayConfig', () => {
  it('тип получает своё название и цвет', () => {
    const config = buildEventDisplayConfig(eventType([]))
    expect(config.displayName).toBe('Кормление')
    expect(config.color).toBe('orange')
  })
})

describe('buildEventDisplayConfigs', () => {
  it('в карте есть лекарства и каждый тип', () => {
    const map = buildEventDisplayConfigs([eventType([])])
    expect(map.medications).toBe(MEDICATIONS_DISPLAY)
    expect(map.food.displayName).toBe('Кормление')
  })
})
