import { describe, expect, it } from 'vitest'
import type { QueryClient } from '@tanstack/react-query'
import { refreshAfterIntake, refreshMedicationViews } from '../../src/utils/intakeViews'

/** A query client that only records which queries were invalidated. */
function recorder() {
  const invalidated: string[][] = []
  const client = {
    invalidateQueries: (opts: { predicate?: (q: { queryKey: readonly unknown[] }) => boolean }) => {
      const keys = KEYS.filter((key) => !opts.predicate || opts.predicate({ queryKey: key }))
      invalidated.push(...keys)
      return Promise.resolve()
    },
  } as unknown as QueryClient
  return { client, invalidated }
}

const KEYS: readonly unknown[][] = [
  ['medications', 'pet1'],
  ['medical-card', 'pet1'],
  ['medical-card', 'pet1', 'alerts'],
  ['timeline', 'pet1'],
  ['history-timeline', 'pet1'],
  ['stats', 'pet1'],
  ['pet-summary', 'pet1'],
  ['pets'],
  ['history-timeline', 'pet1', 'all'],
  ['some-other-view', 'pet1'],
]

describe('refreshMedicationViews', () => {
  it('обновляет всё, где показан курс', () => {
    const { client, invalidated } = recorder()
    refreshMedicationViews(client)
    expect(invalidated).toContainEqual(['medications', 'pet1'])
    expect(invalidated).toContainEqual(['timeline', 'pet1'])
    expect(invalidated).toContainEqual(['history-timeline', 'pet1'])
    expect(invalidated).toContainEqual(['pets'])
  })

  it('не трогает чужое', () => {
    const { client, invalidated } = recorder()
    refreshMedicationViews(client)
    expect(invalidated).not.toContainEqual(['some-other-view', 'pet1'])
  })
})

describe('refreshAfterIntake', () => {
  it('обновляет ленту и историю: там отметка отдельной строкой', () => {
    const { client, invalidated } = recorder()
    refreshAfterIntake(client)
    expect(invalidated).toContainEqual(['timeline', 'pet1'])
    expect(invalidated).toContainEqual(['history-timeline', 'pet1'])
    expect(invalidated).toContainEqual(['medications', 'pet1'])
  })

  it('медкарту обновляет только точка на вкладке «Лекарства»', () => {
    // The card holds courses, not doses: only the dot on the «Лекарства» tab moves.
    const { client, invalidated } = recorder()
    refreshAfterIntake(client)
    expect(invalidated).not.toContainEqual(['medical-card', 'pet1'])
    expect(invalidated).toContainEqual(['medical-card', 'pet1', 'alerts'])
  })
})
