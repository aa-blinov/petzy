import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAuth } from '../../src/hooks/useAuth'

vi.mock('../../src/services/auth.service', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    getSession: vi.fn(() => Promise.resolve({ username: 'demo', is_admin: false })),
  },
}))

vi.mock('../../src/services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/services/api')>()
  return {
    ...actual,
    beginSignOut: vi.fn(actual.beginSignOut),
    clearApiCaches: vi.fn(actual.clearApiCaches),
    clearLocalAuthState: vi.fn(actual.clearLocalAuthState),
    resetSessionExpired: vi.fn(actual.resetSessionExpired),
  }
})

vi.mock('../../src/utils/pushNotifications', () => ({
  unsubscribeBeforeSignOut: vi.fn(() => Promise.resolve()),
  currentPushEndpoint: vi.fn(() => Promise.resolve('https://push.example/endpoint-1')),
}))

import { authService } from '../../src/services/auth.service'

const login = authService.login as unknown as ReturnType<typeof vi.fn>
const register = authService.register as unknown as ReturnType<typeof vi.fn>
const logout = authService.logout as unknown as ReturnType<typeof vi.fn>

const USERNAME_KEY = 'petzy:auth:username'

function wrapper(client: QueryClient, path: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={[path]}>
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

describe('useAuth', () => {
  beforeEach(() => {
    login.mockReset()
    register.mockReset()
    logout.mockReset()
    login.mockResolvedValue({ message: 'ok' })
    register.mockResolvedValue(undefined)
    logout.mockResolvedValue(undefined)
    window.localStorage.clear()
  })

  it('после входа имя запоминается', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.login({ username: 'demo', password: 'пароль' })
    })
    expect(window.localStorage.getItem(USERNAME_KEY)).toBe('demo')
  })

  it('неудачный вход забывает имя', async () => {
    window.localStorage.setItem(USERNAME_KEY, 'прошлый')
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    login.mockRejectedValue(new Error('не тот пароль'))
    await act(async () => {
      await expect(result.current.login({ username: 'demo', password: 'пароль' })).rejects.toThrow('не тот пароль')
    })
    expect(window.localStorage.getItem(USERNAME_KEY)).toBeNull()
  })

  it('после регистрации имя запоминается в нижнем регистре', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.register({ username: ' Demo ', password: 'пароль', full_name: 'Демо', privacy_consent: true })
    })
    expect(window.localStorage.getItem(USERNAME_KEY)).toBe('demo')
  })

  it('выход уводит на страницу входа', async () => {
    const { result } = renderHook(() => ({ auth: useAuth(), path: useLocation().pathname }), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.auth.logout()
    })
    expect(result.current.path).toBe('/login')
  })

  it('выход называет адрес подписки на напоминания, чтобы сервер убрал её вместе со входом', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.logout()
    })
    expect(logout).toHaveBeenCalledWith({ everywhere: false, pushEndpoint: 'https://push.example/endpoint-1' })
  })

  it('выход забывает имя и выбранного питомца', async () => {
    window.localStorage.setItem(USERNAME_KEY, 'demo')
    window.localStorage.setItem('selectedPetId', JSON.stringify('p1'))
    window.localStorage.setItem('selectedPetName', JSON.stringify('Рекс'))
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.logout()
    })
    expect(window.localStorage.getItem(USERNAME_KEY)).toBeNull()
    expect(window.localStorage.getItem('selectedPetId')).toBeNull()
    expect(window.localStorage.getItem('selectedPetName')).toBeNull()
  })

  it('выход не застревает, когда сервер не ответил', async () => {
    window.localStorage.setItem(USERNAME_KEY, 'demo')
    logout.mockRejectedValue(new Error('сервер не ответил'))
    const { result } = renderHook(() => ({ auth: useAuth(), path: useLocation().pathname }), { wrapper: wrapper(client(), '/') })
    await act(async () => {
      await result.current.auth.logout()
    })
    expect(result.current.path).toBe('/login')
    expect(window.localStorage.getItem(USERNAME_KEY)).toBeNull()
  })

  it('на странице входа загрузка не показывается', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/login') })
    expect(result.current.isLoading).toBe(false)
  })

  it('на защищённой странице загрузка видна, пока сессия не известна', () => {
    const { result } = renderHook(() => useAuth(), { wrapper: wrapper(client(), '/') })
    expect(result.current.isLoading).toBe(true)
  })
})
