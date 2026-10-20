import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { usePendingIntakes } from '../../src/utils/offlineIntakes'

// The queue lives in the browser's storage, and Node keeps an inert one of its own
// that shadows the page's, so the page's storage is taken first.
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

vi.mock('../../src/services/auth.service', () => ({
  authService: { getSession: () => Promise.resolve({ username: 'demo' }) },
  type: {},
}))

const KEY = 'petzy:pendingIntakes'

afterEach(() => cleanup())

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <MemoryRouter>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </MemoryRouter>
    )
  }
}

/** The queue the person sees, so the test looks at the same thing they do. */
function Show() {
  const pending = usePendingIntakes()
  return (
    <div>
      <span data-testid="count">{pending.length}</span>
      {pending.map((p) => (
        <span key={p.key}>{p.name}</span>
      ))}
    </div>
  )
}

describe('очередь отметок в двух вкладках', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('отметка, сделанная в другой вкладке, видна и здесь', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<Show />, { wrapper: wrapper(client) })
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('0'))

    // What the other tab of this browser leaves in the storage.
    const other = {
      key: 'k1',
      owner: 'demo',
      medicationId: 'm1',
      name: 'Дронтал',
      input: { date: '2026-10-19', time: '09:00' },
    }
    localStorage.setItem(KEY, JSON.stringify([other]))
    window.dispatchEvent(new StorageEvent('storage', { key: KEY, newValue: JSON.stringify([other]) }))

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('1'))
    expect(screen.getByText('Дронтал')).toBeTruthy()
  })

  it('чужая отметка в другой вкладке не приходит под моим логином', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<Show />, { wrapper: wrapper(client) })
    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('0'))

    const other = {
      key: 'k2',
      owner: 'someone-else',
      medicationId: 'm2',
      name: 'Чужая',
      input: { date: '2026-10-19', time: '09:00' },
    }
    localStorage.setItem(KEY, JSON.stringify([other]))
    window.dispatchEvent(new StorageEvent('storage', { key: KEY, newValue: JSON.stringify([other]) }))

    await waitFor(() => expect(screen.getByTestId('count').textContent).toBe('0'))
  })
})
