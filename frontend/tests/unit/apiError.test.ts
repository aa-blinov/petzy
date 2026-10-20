import { afterEach, describe, expect, it, vi } from 'vitest'
import { getApiErrorMessage, NO_ANSWER_MESSAGE, OFFLINE_MESSAGE } from '../../src/utils/apiError'

function axiosError(data: unknown, status = 400): unknown {
  return { isAxiosError: true, response: { data, status } }
}

function noResponse(): unknown {
  return { isAxiosError: true, response: undefined }
}

describe('getApiErrorMessage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('отдаёт текст сервера из error', () => {
    expect(getApiErrorMessage(axiosError({ error: 'Питомец не найден' }), 'запасной')).toBe('Питомец не найден')
  })

  it('отдаёт текст сервера из message', () => {
    expect(getApiErrorMessage(axiosError({ message: 'Не хватает прав' }), 'запасной')).toBe('Не хватает прав')
  })

  it('отдаёт текст сервера из detail', () => {
    expect(getApiErrorMessage(axiosError({ detail: 'Поле name обязательно' }), 'запасной')).toBe('Поле name обязательно')
  })

  it('тело без текста берёт запасной', () => {
    expect(getApiErrorMessage(axiosError({}), 'запасной')).toBe('запасной')
  })

  it('тело-список берёт запасной', () => {
    expect(getApiErrorMessage(axiosError(['a', 'b']), 'запасной')).toBe('запасной')
  })

  it('без ответа сервера при отсутствии связи говорит о связи', () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false)
    expect(getApiErrorMessage(noResponse(), 'запасной')).toBe(OFFLINE_MESSAGE)
  })

  it('без ответа сервера при наличии связи говорит, что сервер не ответил', () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    expect(getApiErrorMessage(noResponse(), 'запасной')).toBe(NO_ANSWER_MESSAGE)
  })

  it('на падении сервера говорит, что сервер не ответил', () => {
    expect(getApiErrorMessage(axiosError('Bad Gateway', 502), 'запасной')).toBe(NO_ANSWER_MESSAGE)
  })

  it('на чужой ошибке берёт запасной', () => {
    expect(getApiErrorMessage(new Error('сбой'), 'запасной')).toBe('запасной')
  })

  it('на ошибке без ответа берёт запасной', () => {
    expect(getApiErrorMessage('просто строка', 'запасной')).toBe('запасной')
  })
})
