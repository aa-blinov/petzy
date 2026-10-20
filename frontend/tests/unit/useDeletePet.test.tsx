import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useDeletePet } from '../../src/hooks/useDeletePet'
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

import api from '../../src/services/api'
import { petsService } from '../../src/services/pets.service'

const getPets = petsService.getPets as unknown as ReturnType<typeof vi.fn>
const serverDelete = api.delete as unknown as ReturnType<typeof vi.fn>

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

/** Что видит человек: список питомцев, выбор и кнопка удаления */
function usePetsAndDelete() {
  const pet = usePet()
  const remove = useDeletePet()
  return { ...pet, remove }
}

afterEach(() => cleanup())

// Node держит собственное пустое хранилище и закрывает им хранилище страницы,
// поэтому берётся сначала то, что у страницы.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

describe('useDeletePet', () => {
  beforeEach(() => {
    // Полоса с «Отменить» от прошлого теста: закрытая полоса отправляет ожидающее удаление
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
    getPets.mockReset()
    serverDelete.mockReset()
    serverDelete.mockResolvedValue({})
    window.localStorage.clear()
  })

  it('питомец уходит из списка сразу', async () => {
    getPets.mockResolvedValue([pet('p1', 'Рекс')])
    const { result } = renderHook(() => usePetsAndDelete(), { wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })) })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.remove(pet('p1', 'Рекс'))
    })
    expect(result.current.pets.map((p) => p._id)).toEqual([])
  })

  it('до истечения времени сервер не спрашивается', async () => {
    getPets.mockResolvedValue([pet('p2', 'Рекс')])
    const { result } = renderHook(() => usePetsAndDelete(), { wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })) })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.remove(pet('p2', 'Рекс'))
    })
    expect(serverDelete).not.toHaveBeenCalled()
  })

  it('отмена возвращает питомца в список', async () => {
    getPets.mockResolvedValue([pet('p3', 'Рекс')])
    const { result } = renderHook(() => usePetsAndDelete(), { wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })) })
    await waitFor(() => expect(result.current.pets.length).toBe(1))
    await act(async () => {
      await result.current.remove(pet('p3', 'Рекс'))
    })
    await act(async () => {
      await runSnackbarAction(getSnackbar()!.id)
    })
    await waitFor(() => expect(result.current.pets.map((p) => p._id)).toEqual(['p3']))
  })

  it('отмена возвращает выбранного питомца в выбор', async () => {
    getPets.mockResolvedValue([pet('p4', 'Рекс'), pet('p5', 'Бар')])
    const { result } = renderHook(() => usePetsAndDelete(), { wrapper: wrapper(new QueryClient({ defaultOptions: { queries: { retry: false } } })) })
    await waitFor(() => expect(result.current.selectedPetId).toBe('p4'))
    await act(async () => {
      await result.current.remove(pet('p4', 'Рекс'))
    })
    await act(async () => {
      await runSnackbarAction(getSnackbar()!.id)
    })
    await waitFor(() => expect(result.current.selectedPetId).toBe('p4'))
  })
})
