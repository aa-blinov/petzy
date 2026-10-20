import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/** Service worker браузера: то, о чём модуль спрашивает. */
class FakeServiceWorker extends EventTarget {
  controller: unknown = null
  update = vi.fn(async () => undefined)
  getRegistration = vi.fn(async () => ({ update: this.update }))
}

/** Свежая копия модуля: у него своя память о готовом обновлении. */
async function freshModule() {
  vi.resetModules()
  return await import('../../src/utils/swUpdate')
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  Reflect.deleteProperty(navigator, 'serviceWorker')
})

describe('новый выпуск приложения', () => {
  it('первая установка не считается обновлением', async () => {
    const worker = new FakeServiceWorker()
    Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
    const swUpdate = await freshModule()
    swUpdate.watchForUpdates()
    worker.dispatchEvent(new Event('controllerchange'))
    expect(swUpdate.isUpdateReady()).toBe(false)
  })

  it('новый worker перехватил страницу: приложение предлагает обновиться', async () => {
    const worker = new FakeServiceWorker()
    worker.controller = { scriptURL: '/sw.js' }
    Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
    const swUpdate = await freshModule()
    const listener = vi.fn()
    swUpdate.subscribeUpdate(listener)
    swUpdate.watchForUpdates()
    worker.dispatchEvent(new Event('controllerchange'))
    expect(swUpdate.isUpdateReady()).toBe(true)
    expect(listener).toHaveBeenCalled()
  })

  it('отписавшийся подписчик обновления не слышит', async () => {
    const worker = new FakeServiceWorker()
    worker.controller = { scriptURL: '/sw.js' }
    Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
    const swUpdate = await freshModule()
    const listener = vi.fn()
    swUpdate.subscribeUpdate(listener)()
    swUpdate.watchForUpdates()
    worker.dispatchEvent(new Event('controllerchange'))
    expect(listener).not.toHaveBeenCalled()
    expect(swUpdate.isUpdateReady()).toBe(true)
  })

  it('при возврате на экран проверяется новая версия', async () => {
    const worker = new FakeServiceWorker()
    Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
    const swUpdate = await freshModule()
    swUpdate.watchForUpdates()
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(worker.update).toHaveBeenCalled()
  })

  it('раз в час новая версия проверяется сама', async () => {
    const worker = new FakeServiceWorker()
    Object.defineProperty(navigator, 'serviceWorker', { value: worker, configurable: true })
    const swUpdate = await freshModule()
    swUpdate.watchForUpdates()
    await vi.advanceTimersByTimeAsync(60 * 60 * 1000)
    expect(worker.update).toHaveBeenCalled()
  })

  it('в браузере без service worker ничего не ломается', async () => {
    const swUpdate = await freshModule()
    expect(() => swUpdate.watchForUpdates()).not.toThrow()
    expect(swUpdate.isUpdateReady()).toBe(false)
  })
})
