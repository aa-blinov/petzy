import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  getPushSubscriptionState,
  needsHomeScreenForPush,
  rememberedPushState,
  subscribeToPush,
  unsubscribeFromPush,
} from '../../src/utils/pushNotifications'

const pushService = vi.hoisted(() => ({
  getVapidPublicKey: vi.fn(),
  subscribe: vi.fn(),
  unsubscribe: vi.fn(),
}))

vi.mock('../../src/services/push.service', () => ({ pushService }))

/** Подписка браузера на push. */
interface FakeSubscription {
  endpoint: string;
  toJSON: () => { endpoint?: string; keys?: { p256dh?: string; auth?: string } };
  unsubscribe: () => Promise<void>;
}

let subscription: FakeSubscription | null = null
let permission: NotificationPermission = 'granted'
let askedPermission: NotificationPermission = 'granted'

/** Браузер, который умеет push. */
function enablePush() {
  const registration = {
    pushManager: {
      getSubscription: vi.fn(async () => subscription),
      subscribe: vi.fn(async () => {
        if (!subscription) throw new Error('нет подписки')
        return subscription
      }),
    },
  }
  Object.defineProperty(navigator, 'serviceWorker', {
    value: { ready: Promise.resolve(registration) },
    configurable: true,
  })
  Object.defineProperty(window, 'PushManager', { value: class {}, configurable: true })
  globalThis.Notification = {
    get permission() {
      return permission
    },
    requestPermission: vi.fn(async () => askedPermission),
  } as unknown as typeof Notification
}

function makeSubscription(withKeys = true): FakeSubscription {
  return {
    endpoint: 'https://push.example/abc',
    toJSON: () => ({
      endpoint: 'https://push.example/abc',
      keys: withKeys ? { p256dh: 'ключ1', auth: 'ключ2' } : undefined,
    }),
    unsubscribe: vi.fn(async () => {}),
  }
}

// Состояние push лежит в хранилище страницы, а Node держит своё пустое и затеняет им страницу,
// поэтому сначала берём хранилище страницы
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _localStorage?: Storage })._localStorage
  Object.defineProperty(window, 'localStorage', { value: jsdomStorage, configurable: true, writable: true })
})

beforeEach(() => {
  localStorage.clear()
  subscription = null
  permission = 'granted'
  askedPermission = 'granted'
  pushService.getVapidPublicKey.mockReset().mockResolvedValue('BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U')
  pushService.subscribe.mockReset().mockResolvedValue(undefined)
  pushService.unsubscribe.mockReset().mockResolvedValue(undefined)
})

afterEach(() => {
  Reflect.deleteProperty(navigator, 'serviceWorker')
  Reflect.deleteProperty(window, 'PushManager')
  Reflect.deleteProperty(globalThis, 'Notification')
  Reflect.deleteProperty(navigator, 'standalone')
  Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla/5.0 (X11; Linux x86_64) Chrome/120', configurable: true })
  Object.defineProperty(navigator, 'platform', { value: '', configurable: true })
  Object.defineProperty(navigator, 'maxTouchPoints', { value: 0, configurable: true })
})

describe('состояние push', () => {
  it('браузер без push: push не поддерживается', async () => {
    expect(await getPushSubscriptionState()).toBe('unsupported')
  })

  it('уведомления запрещены в настройках браузера', async () => {
    enablePush()
    permission = 'denied'
    expect(await getPushSubscriptionState()).toBe('denied')
  })

  it('подписки ещё нет: push выключен', async () => {
    enablePush()
    expect(await getPushSubscriptionState()).toBe('off')
  })

  it('подписка есть: push включён', async () => {
    enablePush()
    subscription = makeSubscription()
    expect(await getPushSubscriptionState()).toBe('on')
  })

  it('состояние запоминается, чтобы следующий экран не ждал', async () => {
    enablePush()
    expect(await getPushSubscriptionState()).toBe('off')
    // Браузер мог ответить иначе, но экран берёт уже известный ответ
    enablePush()
    subscription = makeSubscription()
    expect(rememberedPushState()).toBe('off')
  })

  it('непонятное значение в хранилище не считается состоянием', () => {
    localStorage.setItem('petzy:push-state', 'что-то не то')
    expect(rememberedPushState()).toBeNull()
  })
})

describe('подписка на push', () => {
  it('напоминания заблокированы в настройках браузера', async () => {
    enablePush()
    permission = 'denied'
    await expect(subscribeToPush()).rejects.toThrow('Напоминания заблокированы в настройках браузера')
  })

  it('разрешения не дали', async () => {
    enablePush()
    permission = 'default'
    askedPermission = 'denied'
    await expect(subscribeToPush()).rejects.toThrow('Напоминания не разрешены')
  })

  it('браузер вернул подписку без ключей', async () => {
    enablePush()
    subscription = makeSubscription(false)
    await expect(subscribeToPush()).rejects.toThrow('Браузер вернул неполные данные подписки')
  })

  it('сервер получает ключи подписки и временную зону', async () => {
    enablePush()
    subscription = makeSubscription()
    await subscribeToPush()
    const sent = pushService.subscribe.mock.calls[0][0] as {
      endpoint: string;
      keys: { p256dh: string; auth: string };
      timezone: string;
    }
    expect(sent.endpoint).toBe('https://push.example/abc')
    expect(sent.keys).toEqual({ p256dh: 'ключ1', auth: 'ключ2' })
    expect(sent.timezone).toBe(Intl.DateTimeFormat().resolvedOptions().timeZone)
  })
})

describe('отписка от push', () => {
  it('если подписки нет, сервер не трогается', async () => {
    enablePush()
    await expect(unsubscribeFromPush()).resolves.toBeUndefined()
    expect(pushService.unsubscribe).not.toHaveBeenCalled()
  })

  it('подписка снимается в браузере, а серверу говорится об этом', async () => {
    enablePush()
    subscription = makeSubscription()
    await unsubscribeFromPush()
    expect(subscription.unsubscribe).toHaveBeenCalled()
    expect(pushService.unsubscribe).toHaveBeenCalledWith('https://push.example/abc')
    expect(rememberedPushState()).toBe('off')
  })
})

describe('iPhone и iPad', () => {
  /** Браузер без push: так он и выглядит в обычной вкладке Safari. */
  function withoutPushManager() {
    Object.defineProperty(window, 'matchMedia', {
      value: () => ({ matches: false }),
      configurable: true,
    })
  }

  it('в обычной вкладке Safari на iPhone push не заработает', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1',
      configurable: true,
    })
    expect(needsHomeScreenForPush()).toBe(true)
  })

  it('в iPhone на iOS 16.3 push ещё нельзя', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_3 like Mac OS X) AppleWebKit/605.1.15 Version/16.3 Mobile/15E148 Safari/604.1',
      configurable: true,
    })
    expect(needsHomeScreenForPush()).toBe(false)
  })

  it('в приложении на домашнем экране push работает', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1',
      configurable: true,
    })
    Object.defineProperty(navigator, 'standalone', { value: true, configurable: true })
    expect(needsHomeScreenForPush()).toBe(false)
  })

  it('на Android домашний экран не нужен', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
      configurable: true,
    })
    expect(needsHomeScreenForPush()).toBe(false)
  })

  it('в Safari на iPad push не заработает', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15',
      configurable: true,
    })
    Object.defineProperty(navigator, 'platform', { value: 'MacIntel', configurable: true })
    Object.defineProperty(navigator, 'maxTouchPoints', { value: 5, configurable: true })
    expect(needsHomeScreenForPush()).toBe(true)
  })

  it('на настоящем Mac домашний экран не нужен', () => {
    withoutPushManager()
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15',
      configurable: true,
    })
    Object.defineProperty(navigator, 'platform', { value: 'MacIntel', configurable: true })
    expect(needsHomeScreenForPush()).toBe(false)
  })
})
