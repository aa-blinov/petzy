import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePet } from '../../src/hooks/usePet'
import { closeSnackbar, getSnackbar } from '../../src/utils/snackbar'
import type { Pet } from '../../src/services/pets.service'

vi.mock('../../src/services/pets.service', () => ({
  petsService: { getPets: vi.fn() },
}))

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: vi.fn(() => Promise.resolve({ username: 'demo', is_admin: false })) },
}))

import { petsService } from '../../src/services/pets.service'

const getPets = petsService.getPets as unknown as ReturnType<typeof vi.fn>

// Node держит собственное пустое хранилище и закрывает им хранилище страницы,
// поэтому берётся сначала то, что у страницы.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

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

function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

afterEach(() => cleanup())

describe('usePet', () => {
  beforeEach(() => {
    getPets.mockReset()
    getPets.mockResolvedValue([])
    window.localStorage.clear()
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
  })

  it('когда питомец не выбран, выбирается первый', async () => {
    getPets.mockResolvedValue([pet('p1', 'Рекс'), pet('p2', 'Бар')])
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.selectedPetId).toBe('p1'))
    expect(result.current.selectedPetName).toBe('Рекс')
  })

  it('выбранный питомец, которого больше нет, заменяется первым', async () => {
    window.localStorage.setItem('selectedPetId', JSON.stringify('p-old'))
    window.localStorage.setItem('selectedPetName', JSON.stringify('Рекс'))
    getPets.mockResolvedValue([pet('p1', 'Рекс')])
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.selectedPetId).toBe('p1'))
    expect(getSnackbar()?.message).toContain('больше вам недоступен')
  })

  it('питомец, удалённый самим человеком, не вызывает уведомления', async () => {
    const { expectPetGone } = await import('../../src/hooks/usePet')
    expectPetGone('p-mine')
    window.localStorage.setItem('selectedPetId', JSON.stringify('p-mine'))
    window.localStorage.setItem('selectedPetName', JSON.stringify('Рекс'))
    getPets.mockResolvedValue([])
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.isFetched).toBe(true))
    expect(result.current.selectedPetId).toBeNull()
    expect(getSnackbar()?.message).toBeUndefined()
  })

  it('имя выбранного питомца следует за переименованием', async () => {
    window.localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    window.localStorage.setItem('selectedPetName', JSON.stringify('Рекс'))
    getPets.mockResolvedValue([pet('p1', 'Рекс-младший')])
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.selectedPetName).toBe('Рекс-младший'))
  })

  it('неудачный запрос списка не значит, что питомцев нет', async () => {
    getPets.mockRejectedValue(new Error('сервер не ответил'))
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.isError).toBe(true))
  })

  it('смена питомца обновляет данные питомца', async () => {
    getPets.mockResolvedValue([pet('p1', 'Рекс'), pet('p2', 'Бар')])
    const meds = vi.fn(() => Promise.resolve([]))
    const c = client()
    function Probe() {
      useQuery({ queryKey: ['medications', 'p1'], queryFn: meds })
      return null
    }
    const { result } = renderHook(() => usePet(), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <MemoryRouter initialEntries={['/']}>
          <QueryClientProvider client={c}>
            <Probe />
            {children}
          </QueryClientProvider>
        </MemoryRouter>
      ),
    })
    await waitFor(() => expect(meds).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(result.current.pets.length).toBe(2))
    act(() => {
      result.current.selectPet(pet('p2', 'Бар'))
    })
    await waitFor(() => expect(meds).toHaveBeenCalledTimes(2))
  })

  it('смена питомца не перезапрашивает сам список питомцев', async () => {
    getPets.mockResolvedValue([pet('p1', 'Рекс'), pet('p2', 'Бар')])
    const { result } = renderHook(() => usePet(), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.pets.length).toBe(2))
    const callsBefore = getPets.mock.calls.length
    act(() => {
      result.current.selectPet(pet('p2', 'Бар'))
    })
    await waitFor(() => expect(result.current.selectedPetId).toBe('p2'))
    expect(getPets.mock.calls.length).toBe(callsBefore)
  })
})
