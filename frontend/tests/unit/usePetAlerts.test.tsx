import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { alertText, usePetAlerts } from '../../src/hooks/usePetAlerts'
import type { Pet } from '../../src/services/pets.service'

vi.mock('../../src/services/medicalCard.service', () => ({
  medicalCardService: { alerts: vi.fn() },
}))

import { medicalCardService } from '../../src/services/medicalCard.service'

const alerts = medicalCardService.alerts as unknown as ReturnType<typeof vi.fn>

const reks: Pet = { _id: 'p1', name: 'Рекс', owner: 'demo' }
const bar: Pet = { _id: 'p2', name: 'Бар', owner: 'demo' }

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}

afterEach(() => cleanup())

describe('usePetAlerts', () => {
  beforeEach(() => {
    alerts.mockReset()
    alerts.mockResolvedValue({ vaccination: false, parasite: false, medication: false })
  })

  it('у каждого питомца свой ответ', async () => {
    alerts.mockImplementation((petId: string) =>
      Promise.resolve({
        vaccination: petId === 'p1',
        parasite: false,
        medication: false,
      }),
    )
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => usePetAlerts([reks, bar], true), { wrapper: wrapper(client) })
    await waitFor(() => expect(result.current.size).toBe(2))
    expect(result.current.get('p1')?.vaccination).toBe(true)
    expect(result.current.get('p2')?.vaccination).toBe(false)
  })

  it('питомец, чей ответ ещё не пришёл, в карте отсутствует', async () => {
    alerts.mockImplementation((petId: string) =>
      petId === 'p1' ? Promise.resolve({ vaccination: true, parasite: false, medication: false }) : new Promise(() => {}),
    )
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => usePetAlerts([reks, bar], true), { wrapper: wrapper(client) })
    await waitFor(() => expect(result.current.size).toBe(1))
    expect(result.current.has('p1')).toBe(true)
    expect(result.current.has('p2')).toBe(false)
  })

  it('пока ответы не спрашиваются, карта пустая', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => usePetAlerts([reks, bar], false), { wrapper: wrapper(client) })
    expect(result.current.size).toBe(0)
    expect(alerts).not.toHaveBeenCalled()
  })
})

describe('alertText', () => {
  it('без ответа ни слова не говорится', () => {
    expect(alertText(undefined)).toBeNull()
  })

  it('когда всё в порядке, ни слова не говорится', () => {
    expect(alertText({ vaccination: false, parasite: false, medication: false })).toBeNull()
  })

  it('просроченная прививка говорится своей фразой', () => {
    expect(alertText({ vaccination: true, parasite: false, medication: false })).toBe('Просрочена прививка')
  })

  it('просроченная обработка говорится своей фразой', () => {
    expect(alertText({ vaccination: false, parasite: true, medication: false })).toBe('Просрочена обработка')
  })

  it('прививка и обработка вместе говорятся одной фразой', () => {
    expect(alertText({ vaccination: true, parasite: true, medication: false })).toBe('Просрочены прививка и обработка')
  })

  it('неотмеченный приём лекарства говорится своей фразой', () => {
    expect(alertText({ vaccination: false, parasite: false, medication: true })).toBe('Не отмечен приём лекарства')
  })

  it('прививка и лекарство говорятся двумя фразами', () => {
    expect(alertText({ vaccination: true, parasite: false, medication: true })).toBe(
      'Просрочена прививка. Не отмечен приём лекарства',
    )
  })
})
