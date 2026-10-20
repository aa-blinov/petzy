import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { useEventTypes } from '../../src/hooks/useEventTypes'

vi.mock('../../src/services/eventTypes.service', () => ({
  eventTypesService: { list: vi.fn() },
}))

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: vi.fn(() => Promise.resolve({ username: 'demo', is_admin: false })) },
}))

import { eventTypesService } from '../../src/services/eventTypes.service'

const list = eventTypesService.list as unknown as ReturnType<typeof vi.fn>

const feeding = {
  key: 'feeding',
  label: 'Кормление',
  icon: 'bowl',
  color: 'blue',
  is_builtin: true,
  fields: [],
  chart: { kind: 'count' },
}

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

describe('useEventTypes', () => {
  beforeEach(() => {
    list.mockReset()
    list.mockResolvedValue([feeding])
  })

  it('на странице входа список типов не спрашивается', async () => {
    const { result } = renderHook(() => useEventTypes(), { wrapper: wrapper(client(), '/login') })
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(list).not.toHaveBeenCalled()
    expect(result.current.eventTypes).toEqual([])
  })

  it('на защищённой странице список типов приходит', async () => {
    const { result } = renderHook(() => useEventTypes(), { wrapper: wrapper(client(), '/') })
    await waitFor(() => expect(result.current.eventTypes.length).toBe(1))
    expect(result.current.eventTypes[0].label).toBe('Кормление')
  })

  it('тип ищется по ключу', async () => {
    const { result } = renderHook(() => useEventTypes(), { wrapper: wrapper(client(), '/') })
    await waitFor(() => expect(result.current.eventTypesByKey['feeding']).toBeTruthy())
    expect(result.current.eventTypesByKey['feeding'].label).toBe('Кормление')
  })

  it('неудачный запрос виден, а не выглядит как пустой список', async () => {
    list.mockRejectedValue(new Error('сервер не ответил'))
    const { result } = renderHook(() => useEventTypes(), { wrapper: wrapper(client(), '/') })
    await waitFor(() => expect(result.current.error).toBeTruthy())
    expect(result.current.error).toBeInstanceOf(Error)
  })
})
