import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePetTilesSettings } from '../../src/hooks/usePetTilesSettings'
import { DEFAULT_TILES_SETTINGS } from '../../src/utils/tilesConfig'
import { closeSnackbar, getSnackbar } from '../../src/utils/snackbar'
import type { Pet } from '../../src/services/pets.service'

vi.mock('../../src/services/pets.service', () => ({
  petsService: { getPets: vi.fn(), updatePet: vi.fn() },
}))

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: vi.fn(() => Promise.resolve({ username: 'demo', is_admin: false })) },
}))

import { petsService } from '../../src/services/pets.service'

const getPets = petsService.getPets as unknown as ReturnType<typeof vi.fn>
const updatePet = petsService.updatePet as unknown as ReturnType<typeof vi.fn>

/** Что лежит на сервере: запросы отвечают тем, что там есть */
let serverPet: Pet = {
  _id: 'p1',
  name: 'Рекс',
  owner: 'demo',
  tiles_settings: { order: ['weight', 'feeding'], visible: { weight: true, feeding: false } },
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

// Node держит собственное пустое хранилище и закрывает им хранилище страницы,
// поэтому берётся сначала то, что у страницы.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

describe('usePetTilesSettings', () => {
  beforeEach(() => {
    serverPet = {
      _id: 'p1',
      name: 'Рекс',
      owner: 'demo',
      tiles_settings: { order: ['weight', 'feeding'], visible: { weight: true, feeding: false } },
    }
    getPets.mockReset()
    updatePet.mockReset()
    getPets.mockImplementation(() => Promise.resolve([serverPet]))
    updatePet.mockImplementation((_id: string, patch: Partial<Pet>) => {
      serverPet = { ...serverPet, ...patch }
      return Promise.resolve(serverPet)
    })
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
  })

  it('настройки плиток берутся у питомца', async () => {
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.order).toEqual(['weight', 'feeding']))
    expect(result.current.tilesSettings.visible).toEqual({ weight: true, feeding: false })
  })

  it('у питомца без настроек берутся общие', async () => {
    serverPet = { _id: 'p1', name: 'Рекс', owner: 'demo' }
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings).toEqual(DEFAULT_TILES_SETTINGS))
  })

  it('переключение одной плитки не трогает остальные', async () => {
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.visible.feeding).toBe(false))
    act(() => {
      result.current.toggleVisibility('feeding', true)
    })
    await waitFor(() => expect(result.current.tilesSettings.visible.feeding).toBe(true))
    expect(result.current.tilesSettings.visible.weight).toBe(true)
    expect(result.current.tilesSettings.order).toEqual(['weight', 'feeding'])
  })

  it('новый порядок не трогает видимость', async () => {
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.order.length).toBe(2))
    act(() => {
      result.current.updateOrder(['feeding', 'weight'])
    })
    await waitFor(() => expect(result.current.tilesSettings.order).toEqual(['feeding', 'weight']))
    expect(result.current.tilesSettings.visible).toEqual({ weight: true, feeding: false })
  })

  it('изменение видно сразу, до ответа сервера', async () => {
    updatePet.mockImplementation(() => new Promise(() => {}))
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.visible.feeding).toBe(false))
    act(() => {
      result.current.toggleVisibility('feeding', true)
    })
    await waitFor(() => expect(result.current.tilesSettings.visible.feeding).toBe(true))
  })

  it('серверу уходят и порядок, и видимость', async () => {
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.order.length).toBe(2))
    act(() => {
      result.current.updateOrder(['feeding'])
    })
    await waitFor(() => expect(updatePet).toHaveBeenCalled())
    expect(updatePet).toHaveBeenCalledWith('p1', {
      tiles_settings: { order: ['feeding'], visible: { weight: true, feeding: false } },
    })
  })

  it('отказ сервера говорит, что сохранить не вышло', async () => {
    updatePet.mockRejectedValue(new Error('сервер не ответил'))
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.order.length).toBe(2))
    act(() => {
      result.current.updateOrder(['feeding'])
    })
    await waitFor(() => expect(getSnackbar()?.message).toBe('Не удалось сохранить плитки'))
  })

  it('после отказа список возвращается к тому, что у сервера', async () => {
    updatePet.mockRejectedValue(new Error('сервер не ответил'))
    const { result } = renderHook(() => usePetTilesSettings('p1'), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings.order).toEqual(['weight', 'feeding']))
    act(() => {
      result.current.updateOrder(['feeding'])
    })
    await waitFor(() => expect(getSnackbar()?.message).toBe('Не удалось сохранить плитки'))
    await waitFor(() => expect(result.current.tilesSettings.order).toEqual(['weight', 'feeding']))
  })

  it('без выбранного питомца сервер не спрашивается', async () => {
    const { result } = renderHook(() => usePetTilesSettings(null), { wrapper: wrapper(client()) })
    await waitFor(() => expect(result.current.tilesSettings).toEqual(DEFAULT_TILES_SETTINGS))
    act(() => {
      result.current.updateOrder(['feeding'])
    })
    await waitFor(() => expect(getSnackbar()?.message).toBe('Не удалось сохранить плитки'))
    expect(updatePet).not.toHaveBeenCalled()
  })
})
