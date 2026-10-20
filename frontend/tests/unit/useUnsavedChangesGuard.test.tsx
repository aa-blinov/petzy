import { afterEach, describe, expect, it } from 'vitest'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { transferableAbortController } from 'node:util'
import { useUnsavedChangesGuard } from '../../src/hooks/useUnsavedChangesGuard'

// jsdom's AbortSignal is not the one Node's Request takes, and the router builds a Request for every navigation,
// so without this every navigation in the test dies with an error about the signal.
class NodeAbortController {
  #inner = transferableAbortController()
  get signal() {
    return this.#inner.signal
  }
  abort(reason?: unknown) {
    this.#inner.abort(reason)
  }
}
globalThis.AbortController = NodeAbortController as unknown as typeof AbortController

interface Box {
  go?: (path: string) => void
  release?: () => void
}

function mount(dirty: boolean) {
  const box: Box = {}
  function App() {
    const guard = useUnsavedChangesGuard(dirty)
    const navigate = useNavigate()
    useEffect(() => {
      box.go = (path: string) => navigate(path)
      box.release = guard.release
    })
    return <div>{guard.dialog}</div>
  }
  const router = createMemoryRouter([
    { path: '/', element: <App /> },
    { path: '/other', element: <div>другая страница</div> },
  ])
  render(<RouterProvider router={router} />)
  return { box, router }
}

afterEach(() => cleanup())

describe('useUnsavedChangesGuard', () => {
  it('форма с введённым спрашивает перед уходом', async () => {
    const { box, router } = mount(true)
    await act(async () => {
      box.go!('/other')
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    const blocker = [...(router.state.blockers?.values() ?? [])][0]
    expect(blocker?.state).toBe('blocked')
  })

  it('чистая форма уходит без вопроса', async () => {
    const { box, router } = mount(false)
    await act(async () => {
      box.go!('/other')
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/other'))
  })

  it('смена запроса на той же странице не спрашивает', async () => {
    const { box, router } = mount(true)
    await act(async () => {
      box.go!('/?tab=weight')
    })
    await waitFor(() => expect(router.state.location.search).toBe('?tab=weight'))
  })

  it('после освобождения вопрос не задаётся', async () => {
    const { box, router } = mount(true)
    await act(async () => {
      box.release!()
    })
    await act(async () => {
      box.go!('/other')
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/other'))
  })

  it('браузер предупреждает, пока форма грязная', () => {
    mount(true)
    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('чистая форма браузеру не мешает', () => {
    mount(false)
    const event = new Event('beforeunload', { cancelable: true })
    window.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(false)
  })
})
