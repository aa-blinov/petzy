import { afterEach, describe, expect, it, vi } from 'vitest'
import { initSentry, scrubUrl } from '../../src/utils/observability'

const sentry = vi.hoisted(() => ({
  init: vi.fn(),
  replay: vi.fn((options: Record<string, unknown>) => ({ name: 'Replay', options })),
}))

vi.mock('@sentry/react', () => ({
  init: sentry.init,
  setUser: vi.fn(),
  captureException: vi.fn(),
  browserTracingIntegration: () => ({ name: 'BrowserTracing' }),
  replayIntegration: sentry.replay,
}))

/** То, что модуль отдал Sentry при включении. */
interface SentryOptions {
  dataCollection: { httpHeaders: { request: { deny: string[] } } };
  beforeSend: (event: Record<string, unknown>) => Record<string, unknown>;
  beforeSendSpan: (span: { name: string; attributes: Record<string, unknown> }) => { name: string; attributes: Record<string, unknown> };
}

function options(): SentryOptions {
  const call = sentry.init.mock.calls.at(-1)
  if (!call) throw new Error('Sentry не включался')
  return call[0] as unknown as SentryOptions
}

afterEach(() => {
  vi.unstubAllEnvs()
  sentry.init.mockClear()
  sentry.replay.mockClear()
})

describe('секрет в адресе', () => {
  it('секрет ссылки на медкарту не уезжает', () => {
    expect(scrubUrl('/share/medical/abc123')).toBe('/share/medical/***')
  })

  it('секрет в адресе запроса медкарты не уезжает', () => {
    expect(scrubUrl('/api/shared/medical-card/xyz789/pdf')).toBe('/api/shared/medical-card/***/pdf')
  })

  it('обычный адрес не меняется', () => {
    expect(scrubUrl('/pets')).toBe('/pets')
  })
})

describe('что уходит в Sentry', () => {
  it('без DSN ничего никуда не уходит', () => {
    initSentry()
    expect(sentry.init).not.toHaveBeenCalled()
  })

  it('в событии адрес чистится до отправки', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ request: { url: '/share/medical/abc123' } })
    const request = event.request as { url: string }
    expect(request.url).toBe('/share/medical/***')
  })

  it('токен из адреса не уезжает', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ request: { url: '/auth/reset?token=abc123' } })
    const request = event.request as { url: string }
    expect(request.url).not.toContain('abc123')
    expect(request.url).toContain('[Filtered]')
  })

  it('куки не уезжают', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ request: { url: '/pets', cookies: 'session=1' } })
    const request = event.request as Record<string, unknown>
    expect(request.cookies).toBeUndefined()
  })

  it('секрет в названии занятого экрана не уезжает', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const span = options().beforeSendSpan({
      name: '/share/medical/abc123',
      attributes: { url: '/api/shared/medical-card/xyz789/pdf' },
    })
    expect(span.name).toBe('/share/medical/***')
    expect(span.attributes.url).toBe('/api/shared/medical-card/***/pdf')
  })

  it('текст на экране не попадает в запись', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const replay = sentry.replay.mock.calls.at(-1)?.[0] as Record<string, unknown>
    expect(replay.maskAllText).toBe(true)
    expect(replay.maskAllInputs).toBe(true)
    expect(replay.blockAllMedia).toBe(true)
  })

  it('заголовок авторизации не собирается', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    expect(options().dataCollection.httpHeaders.request.deny).toContain('authorization')
    expect(options().dataCollection.httpHeaders.request.deny).toContain('cookie')
  })
})

describe('токен из ссылки на сброс пароля', () => {
  it('не уезжает в имени события', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ transaction: '/auth/reset?token=abc123' })
    expect(event.transaction).not.toContain('abc123')
    expect(event.transaction).toContain('[Filtered]')
  })

  it('не уезжает в сообщении крошки', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ breadcrumbs: [{ message: 'переход /auth/reset?token=abc123' }] })
    expect(event.breadcrumbs?.[0].message).not.toContain('abc123')
  })

  it('не уезжает в данных крошки', () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://key@example.abc/1')
    initSentry()
    const event = options().beforeSend({ breadcrumbs: [{ data: { to: '/auth/reset?token=abc123' } }] })
    expect(event.breadcrumbs?.[0].data?.to).not.toContain('abc123')
  })
})
