import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useAdmin } from '../../src/hooks/useAdmin'

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: vi.fn() },
}))

import { authService } from '../../src/services/auth.service'

const getSession = authService.getSession as unknown as ReturnType<typeof vi.fn>

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter initialEntries={['/']}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    )
  }
}

afterEach(() => cleanup())

describe('useAdmin', () => {
  beforeEach(() => {
    getSession.mockReset()
  })

  it('пока сессия не известна, признак администратора ещё не готов', () => {
    getSession.mockImplementation(() => new Promise(() => {}))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useAdmin(), { wrapper: wrapper(client) })
    expect(result.current.isLoading).toBe(true)
    expect(result.current.isAdmin).toBe(false)
  })

  it('после ответа сессии признак администратора известен', async () => {
    getSession.mockResolvedValue({ username: 'demo', is_admin: true })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useAdmin(), { wrapper: wrapper(client) })
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAdmin).toBe(true)
  })

  it('у обычного пользователя признака администратора нет', async () => {
    getSession.mockResolvedValue({ username: 'demo', is_admin: false })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { result } = renderHook(() => useAdmin(), { wrapper: wrapper(client) })
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.isAdmin).toBe(false)
  })
})
