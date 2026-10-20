import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { filenameFromResponse, saveBlob } from '../../src/utils/download'

type ShareCapable = {
  share?: (data: ShareData) => Promise<void>
  canShare?: (data: ShareData) => boolean
  standalone?: boolean
}

const nav = navigator as Navigator & ShareCapable

/** Ссылки, по которым файл отдан в браузере. */
const clicks: HTMLAnchorElement[] = []

beforeEach(() => {
  clicks.length = 0
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    clicks.push(this)
  })
  // Браузерных API для временных ссылок в тестовой среде нет, их подменяем
  window.URL.createObjectURL = () => 'blob:petzy'
  window.URL.revokeObjectURL = () => {}
})

afterEach(() => {
  vi.restoreAllMocks()
  delete nav.share
  delete nav.canShare
  delete nav.standalone
  delete (window.URL as { createObjectURL?: unknown }).createObjectURL
  delete (window.URL as { revokeObjectURL?: unknown }).revokeObjectURL
})

describe('имя файла из ответа сервера', () => {
  it('кириллическое имя читается как есть', () => {
    expect(filenameFromResponse("attachment; filename*=UTF-8''%D0%A0%D0%B5%D0%BA%D1%81.pdf")).toBe('Рекс.pdf')
  })

  it('в заголовке без имени файла имени нет', () => {
    expect(filenameFromResponse('attachment')).toBeUndefined()
  })

  it('заголовка нет: имени нет', () => {
    expect(filenameFromResponse(undefined)).toBeUndefined()
  })

  it('имя в обычном виде не берётся: сервер присылает кодированное', () => {
    expect(filenameFromResponse('attachment; filename="Рекс.pdf"')).toBeUndefined()
  })
})

describe('файл отдаётся человеку', () => {
  it('в браузере файл скачивается ссылкой с нужным именем', async () => {
    // Системное меню есть и в браузере, но в нём файл открылся бы внутри страницы
    nav.canShare = () => true
    nav.share = vi.fn()
    const saved = await saveBlob('данные', 'Медкарта Рекса.pdf', 'application/pdf')
    expect(saved).toBe(true)
    expect(nav.share).not.toHaveBeenCalled()
    expect(clicks).toHaveLength(1)
    expect(clicks[0].getAttribute('download')).toBe('Медкарта Рекса.pdf')
  })

  it('временная ссылка не остаётся в странице', async () => {
    await saveBlob('данные', 'файл.pdf', 'application/pdf')
    expect(document.querySelector('a[download]')).toBeNull()
  })

  it('в установленном приложении файл уходит в системное меню', async () => {
    nav.standalone = true
    nav.canShare = () => true
    nav.share = vi.fn().mockResolvedValue(undefined)
    const saved = await saveBlob('данные', 'выгрузка.csv', 'text/csv')
    expect(saved).toBe(true)
    expect(clicks).toHaveLength(0)
    const passed = (nav.share as (data: ShareData) => Promise<void>).mock.calls[0][0]
    expect(passed.files?.[0].name).toBe('выгрузка.csv')
    expect(passed.files?.[0].type).toBe('text/csv')
  })

  it('человек закрыл системное меню: файл не сохранён', async () => {
    const closed = new Error('закрыто')
    closed.name = 'AbortError'
    nav.standalone = true
    nav.canShare = () => true
    nav.share = vi.fn().mockRejectedValue(closed)
    const saved = await saveBlob('данные', 'выгрузка.csv', 'text/csv')
    expect(saved).toBe(false)
    expect(clicks).toHaveLength(0)
  })

  it('отказ по другой причине: файл отдаётся ссылкой', async () => {
    nav.standalone = true
    nav.canShare = () => true
    nav.share = vi.fn().mockRejectedValue(new Error('нет места'))
    const saved = await saveBlob('данные', 'выгрузка.csv', 'text/csv')
    expect(saved).toBe(true)
    expect(clicks).toHaveLength(1)
  })

  it('система не может поделиться файлом: файл отдаётся ссылкой', async () => {
    nav.standalone = true
    nav.canShare = () => false
    nav.share = vi.fn()
    const saved = await saveBlob('данные', 'выгрузка.csv', 'text/csv')
    expect(saved).toBe(true)
    expect(nav.share).not.toHaveBeenCalled()
    expect(clicks).toHaveLength(1)
  })
})

describe('имя файла из заголовка', () => {
  it('битая процентная последовательность не роняет загрузку', () => {
    // The header comes from the server and from whatever proxy stands before it.
    expect(filenameFromResponse("attachment; filename*=UTF-8''%E0%A4%A")).toBe('%E0%A4%A')
  })

  it('обычное имя всё равно не берётся', () => {
    // The server sends the encoded form; a plain one is not what the app writes.
    expect(filenameFromResponse('attachment; filename="вес.jpg"')).toBeUndefined()
  })
})
