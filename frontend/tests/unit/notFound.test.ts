import { describe, expect, it } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { isMissing, isPetGone } from '../../src/utils/notFound'
import { stampToRu } from '../../src/utils/recordStamp'

const failed = (status?: number) =>
  new AxiosError('x', undefined, undefined, undefined, status ? ({ status } as AxiosResponse) : undefined)

describe('isMissing', () => {
  it('404 и 422 это «не найдено»: адрес с чужим id отвечает 422', () => {
    expect(isMissing(failed(404))).toBe(true)
    expect(isMissing(failed(422))).toBe(true)
  })

  it('сбой сети и 5xx остаются сбоем, у которого есть «Повторить»', () => {
    expect(isMissing(failed())).toBe(false)
    expect(isMissing(failed(500))).toBe(false)
    expect(isMissing(failed(503))).toBe(false)
    expect(isMissing(new Error('boom'))).toBe(false)
  })

  it('403 для питомца читается как «не найден», для записи нет', () => {
    expect(isPetGone(failed(403))).toBe(true)
    expect(isMissing(failed(403))).toBe(false)
  })
})

describe('stampToRu', () => {
  it('пишет дату как в приложении, ДД.ММ.ГГГГ', () => {
    expect(stampToRu('2026-10-20T12:25:00Z')).toMatch(/^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$/)
    expect(stampToRu('2026-10-20 12:25')).toMatch(/^\d{2}\.10\.2026 \d{2}:25$/)
  })

  it('непонятную строку не ломает', () => {
    expect(stampToRu('вчера')).toBe('вчера')
  })
})
