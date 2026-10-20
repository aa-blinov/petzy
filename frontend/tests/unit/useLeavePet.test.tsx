import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useLeavePet } from '../../src/hooks/useDeletePet'
import { usePet } from '../../src/hooks/usePet'
import { closeSnackbar, getSnackbar, runSnackbarAction } from '../../src/utils/snackbar'
import type { Pet } from '../../src/services/pets.service'

vi.mock('../../src/services/pets.service', () => ({
  petsService: { getPets: vi.fn(), leavePet: vi.fn(), updatePet: vi.fn() },
}))

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: vi.fn(() => Promise.resolve({ username: 'demo', is_admin: false })) },
}))

vi.mock('../../src/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/services/api')>()
  return { ...actual, default: { delete: vi.fn(), defaults: { baseURL: '/api' } } }
})

import { petsService } from '../../src/services/pets.service'

const getPets = petsService.getPets as unknown as ReturnType<typeof vi.fn>
const leavePet = petsService.leavePet as unknown as ReturnType<typeof vi.fn>

function pet(id: string, name: string): Pet {
  return { _id: id, name, owner: 'demo' }
}

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={['/']}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    )
  }
}

/** Что видит человек: список питомцев, выбор и уход из общего доступа */
function usePetsAndLeave() {
  const pet = usePet()
  const leave = useLeavePet()
  return { ...pet, leave }
}

afterEach(() => cleanup())

// Node держит собственное пустое хранилище и закрывает им хранилище страницы,
// поэтому берётся сначала то, что у страницы.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

describe('useLeavePet', () => {
  beforeEach(() => {
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
    getPets.mockReset()
    leavePet.mockReset()
    leavePet.mockResolvedValue({})
    window.localStorage.clear()
  })

  it('питомец уходит из списка сразу', async () => {
    getPets.mockResolvedValue([pet('p1', 'Рекс')])
    const { result } = renderHook(() => usePetsAndLeave(), {
      wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.leave(pet('p1', 'Рекс'))
    })
    expect(result.current.pets.map((p) => p._id)).toEqual([])
  })

  it('до истечения времени сервер не спрашивается', async () => {
    getPets.mockResolvedValue([pet('p2', 'Рекс')])
    const { result } = renderHook(() => usePetsAndLeave(), {
      wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.leave(pet('p2', 'Рекс'))
    })
    expect(leavePet).not.toHaveBeenCalled()
  })

  it('отмена возвращает питомца в список и ничего не отправляет', async () => {
    getPets.mockResolvedValue([pet('p3', 'Рекс')])
    const { result } = renderHook(() => usePetsAndLeave(), {
      wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.leave(pet('p3', 'Рекс'))
    })
    await act(async () => {
      await runSnackbarAction(getSnackbar()!.id)
    })
    await waitFor(() => expect(result.current.pets.map((p) => p._id)).toEqual(['p3']))
    expect(leavePet).not.toHaveBeenCalled()
  })

  it('отказ сервера возвращает питомца в список', async () => {
    getPets.mockResolvedValue([pet('p4', 'Рекс')])
    leavePet.mockRejectedValue(new Error('отказ'))
    const { result } = renderHook(() => usePetsAndLeave(), {
      wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })),
    })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.leave(pet('p4', 'Рекс'))
    })
    await act(async () => {
      await closeSnackbar(getSnackbar()!.id)
    })
    await waitFor(() => expect(result.current.pets.map((p) => p._id)).toEqual(['p4']))
  })
})
