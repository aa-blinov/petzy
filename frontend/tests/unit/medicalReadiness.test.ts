import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import type { MedicalCard, MedicalCardVaccination } from '../../src/services/medicalCard.service'
import type { MedicalRecord } from '../../src/services/medicalRecords.service'
import { getSnackbar } from '../../src/utils/snackbar'
import { cardStatusLine, confirmWithProgress, listWords, missingReadiness, readinessChecks } from '../../src/utils/medicalReadiness'

const get = vi.fn()
vi.mock('../../src/services/medicalCard.service', () => ({
  medicalCardService: { get: (...args: unknown[]) => get(...args) },
}))

function record(over: Partial<MedicalRecord> = {}): MedicalRecord {
  return {
    _id: 'r1',
    pet_id: 'p1',
    kind: 'vaccination',
    date: '2026-01-01',
    title: 'Прививка',
    next_due: null,
    status: 'ok',
    days_left: null,
    superseded: false,
    clinic: null,
    vet: null,
    note: null,
    batch: null,
    target: null,
    protects: null,
    protects_label: null,
    complaint: null,
    diagnosis: null,
    recommendations: null,
    documents: [],
    ...over,
  }
}

function vaccination(over: Partial<MedicalCardVaccination> = {}): MedicalCardVaccination {
  return { id: 'v1', title: 'Прививка', expires_at: null, status: 'valid', days_left: null, note: null, ...over }
}

function card(over: Partial<MedicalCard> = {}): MedicalCard {
  return {
    visit_prep: null,
    pet: { name: 'Рекс', species: 'dog', breed: null, birth_date: null, age_text: null, gender: null, neutered_text: null, health_notes: null },
    profile: { allergies: [], allergies_none_known: false, conditions: [], clinics: [] },
    weight: null,
    records: { vaccination: [], parasite: [], visit: [], procedure: [] },
    record_counts: { vaccination: 0, parasite: 0, visit: 0, procedure: 0 },
    medications: [],
    past_courses: [],
    past_courses_total: 0,
    vaccinations: [],
    documents: [],
    generated_at: '2026-01-01T00:00:00',
    can_edit: true,
    ...over,
  }
}

describe('readinessChecks', () => {
  it('всегда пять проверок', () => {
    expect(readinessChecks(card())).toHaveLength(5)
  })

  it('аллергии закрыты, когда их назвали', () => {
    const checks = readinessChecks(card({ profile: { allergies: [{ substance: 'новотин' }], allergies_none_known: false, conditions: [], clinics: [] } }))
    expect(checks.find((c) => c.key === 'allergies')?.done).toBe(true)
  })

  it('аллергии закрыты, когда сказали, что их нет', () => {
    const checks = readinessChecks(card({ profile: { allergies: [], allergies_none_known: true, conditions: [], clinics: [] } }))
    expect(checks.find((c) => c.key === 'allergies')?.done).toBe(true)
  })

  it('прививка закрыта, когда есть запись', () => {
    const checks = readinessChecks(card({ record_counts: { vaccination: 1, parasite: 0, visit: 0, procedure: 0 } }))
    expect(checks.find((c) => c.key === 'vaccination')?.done).toBe(true)
  })

  it('прививка закрыта, когда есть список прививок', () => {
    const checks = readinessChecks(card({ vaccinations: [vaccination()] }))
    expect(checks.find((c) => c.key === 'vaccination')?.done).toBe(true)
  })

  it('обработка закрыта, когда есть запись', () => {
    const checks = readinessChecks(card({ record_counts: { vaccination: 0, parasite: 1, visit: 0, procedure: 0 } }))
    expect(checks.find((c) => c.key === 'parasite')?.done).toBe(true)
  })

  it('клиника закрыта, когда указан только телефон', () => {
    const checks = readinessChecks(
      card({ profile: { allergies: [], allergies_none_known: false, conditions: [], clinics: [{ phone: '+7 900', doctors: [] }] } }),
    )
    expect(checks.find((c) => c.key === 'clinic')?.done).toBe(true)
  })

  it('клиника не закрыта, когда у врача нет ни имени, ни телефона', () => {
    const checks = readinessChecks(
      card({ profile: { allergies: [], allergies_none_known: false, conditions: [], clinics: [{ doctors: [] }] } }),
    )
    expect(checks.find((c) => c.key === 'clinic')?.done).toBe(false)
  })

  it('вес закрыт, когда он записан', () => {
    const checks = readinessChecks(card({ weight: { latest: { date: '2026-01-01', value: 12.4 }, series: [] } }))
    expect(checks.find((c) => c.key === 'weight')?.done).toBe(true)
  })

  it('в адресе проверки есть питомец', () => {
    const checks = readinessChecks(card(), 'p1')
    expect(checks.find((c) => c.key === 'vaccination')?.to).toContain('/pets/p1/')
  })

  it('у каждой проверки есть подсказка и действие', () => {
    for (const check of readinessChecks(card())) {
      expect(check.label).toBeTruthy()
      expect(check.hint).toBeTruthy()
      expect(check.action).toBeTruthy()
      expect(check.to).toBeTruthy()
    }
  })
})

describe('missingReadiness', () => {
  it('пустая карточка не закрыта ничем', () => {
    expect(missingReadiness(card())).toHaveLength(5)
  })

  it('закрытая проверка из списка уходит', () => {
    const missing = missingReadiness(card({ weight: { latest: { date: '2026-01-01', value: 12.4 }, series: [] } }))
    expect(missing).toHaveLength(4)
    expect(missing).not.toContain('вес')
  })

  it('названия пишутся с маленькой буквы', () => {
    expect(missingReadiness(card())).toContain('аллергии')
  })
})

describe('listWords', () => {
  it('пустой список даёт пустую строку', () => {
    expect(listWords([])).toBe('')
  })

  it('один пункт остаётся один', () => {
    expect(listWords(['вес'])).toBe('вес')
  })

  it('два пункта соединяются через и', () => {
    expect(listWords(['аллергии', 'вес'])).toBe('аллергии и вес')
  })

  it('три пункта читаются списком', () => {
    expect(listWords(['аллергии', 'прививки', 'вес'])).toBe('аллергии, прививки и вес')
  })
})

describe('cardStatusLine', () => {
  it('просроченная прививка поднимает тревогу', () => {
    const line = cardStatusLine(card({ records: { vaccination: [record({ status: 'overdue' })], parasite: [], visit: [], procedure: [] } }), 'p1')
    expect(line).toEqual({ text: 'Прививка просрочена', alert: true })
  })

  it('просроченная обработка поднимает тревогу', () => {
    const line = cardStatusLine(card({ records: { vaccination: [], parasite: [record({ kind: 'parasite', status: 'overdue' })], visit: [], procedure: [] } }), 'p1')
    expect(line).toEqual({ text: 'Обработка просрочена', alert: true })
  })

  it('просроченное и то и другое говорит о обоих', () => {
    const line = cardStatusLine(
      card({
        records: { vaccination: [record({ status: 'overdue' })], parasite: [record({ kind: 'parasite', status: 'overdue' })], visit: [], procedure: [] },
      }),
      'p1',
    )
    expect(line).toEqual({ text: 'Прививка и обработка просрочены', alert: true })
  })

  it('заменённая запись тревогу не поднимает', () => {
    const line = cardStatusLine(card({ records: { vaccination: [record({ status: 'overdue', superseded: true })], parasite: [], visit: [], procedure: [] } }), 'p1')
    expect(line.alert).toBe(false)
  })

  it('истёкшая прививка из списка поднимает тревогу', () => {
    const line = cardStatusLine(card({ vaccinations: [vaccination({ status: 'expired' })] }), 'p1')
    expect(line).toEqual({ text: 'Прививка просрочена', alert: true })
  })

  it('пустая карточка говорит, сколько заполнено', () => {
    expect(cardStatusLine(card(), 'p1')).toEqual({ text: 'Заполнено 0 из 5', alert: false })
  })

  it('полная карточка говорит, что всё заполнено', () => {
    const full = card({
      profile: { allergies: [], allergies_none_known: true, conditions: [], clinics: [{ name: 'ВетДок', doctors: [] }] },
      record_counts: { vaccination: 1, parasite: 1, visit: 0, procedure: 0 },
      weight: { latest: { date: '2026-01-01', value: 12.4 }, series: [] },
    })
    expect(cardStatusLine(full, 'p1')).toEqual({ text: 'Всё заполнено', alert: false })
  })
})

describe('confirmWithProgress', () => {
  it('после сохранения говорит, сколько заполнено', async () => {
    get.mockResolvedValue(
      card({
        profile: { allergies: [], allergies_none_known: true, conditions: [], clinics: [] },
        record_counts: { vaccination: 1, parasite: 0, visit: 0, procedure: 0 },
      }),
    )
    await confirmWithProgress(new QueryClient(), 'p1', 'Прививка добавлена')
    expect(getSnackbar()?.message).toBe('Прививка добавлена. Заполнено 2 из 5')
  })

  it('полная карточка говорит, что главное для врача заполнено', async () => {
    get.mockResolvedValue(
      card({
        profile: { allergies: [], allergies_none_known: true, conditions: [], clinics: [{ name: 'ВетДок', doctors: [] }] },
        record_counts: { vaccination: 1, parasite: 1, visit: 0, procedure: 0 },
        weight: { latest: { date: '2026-01-01', value: 12.4 }, series: [] },
      }),
    )
    await confirmWithProgress(new QueryClient(), 'p1', 'Прививка добавлена')
    expect(getSnackbar()?.message).toBe('Прививка добавлена. Главное для врача заполнено')
  })

  it('когда карточка не пришла, говорит только о сохранённом', async () => {
    get.mockRejectedValue(new Error('сервер не ответил'))
    await confirmWithProgress(new QueryClient(), 'p1', 'Прививка добавлена')
    expect(getSnackbar()?.message).toBe('Прививка добавлена')
  })
})
