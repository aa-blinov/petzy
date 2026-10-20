import { afterEach, describe, expect, it, vi } from 'vitest'
import { setPendingDocumentFile, takePendingDocumentFile } from '../../src/utils/pendingDocumentFile'

const file = new File(['x'], 'снимок.pdf', { type: 'application/pdf' })

describe('pendingDocumentFile', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('без выбранного файла нечего брать', () => {
    expect(takePendingDocumentFile()).toBeNull()
  })

  it('выбранный файл достаётся форме', () => {
    setPendingDocumentFile(file)
    expect(takePendingDocumentFile()).toBe(file)
  })

  it('второй раз файла уже нет', () => {
    setPendingDocumentFile(file)
    takePendingDocumentFile()
    expect(takePendingDocumentFile()).toBeNull()
  })

  it('файл, который прождал пять минут, пропадает', () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    setPendingDocumentFile(file)
    now.mockReturnValue(1_000_000 + 5 * 60 * 1000 + 1)
    expect(takePendingDocumentFile()).toBeNull()
  })

  it('файл, который прождал четыре минуты, остаётся', () => {
    const now = vi.spyOn(Date, 'now').mockReturnValue(1_000_000)
    setPendingDocumentFile(file)
    now.mockReturnValue(1_000_000 + 4 * 60 * 1000)
    expect(takePendingDocumentFile()).toBe(file)
  })

  it('выбор нового файла заменяет прежний', () => {
    const other = new File(['y'], 'анализ.pdf', { type: 'application/pdf' })
    setPendingDocumentFile(file)
    setPendingDocumentFile(other)
    expect(takePendingDocumentFile()).toBe(other)
  })

  it('снятие выбора убирает файл', () => {
    setPendingDocumentFile(file)
    setPendingDocumentFile(null)
    expect(takePendingDocumentFile()).toBeNull()
  })
})
