import { describe, expect, it } from 'vitest'
import type { PetDocument } from '../../src/services/documents.service'
import { documentSearchText, matchesDocumentQuery } from '../../src/utils/documentSearch'

function doc(over: Partial<PetDocument> = {}): PetDocument {
  return {
    _id: 'd1',
    pet_id: 'p1',
    username: 'anna',
    category: 'other',
    title: 'Рентген',
    original_filename: 'xray.jpg',
    content_type: 'image/jpeg',
    file_size: 100,
    created_at: '2026-01-01T00:00:00',
    ...over,
  }
}

describe('documentSearchText', () => {
  it('собирает название, вид, имя файла', () => {
    const text = documentSearchText(doc({ title: 'Рентген', category: 'imaging', original_filename: 'xray.jpg' }))
    expect(text).toContain('рентген')
    expect(text).toContain('снимки')
    expect(text).toContain('xray.jpg')
  })

  it('ё читается как е', () => {
    const text = documentSearchText(doc({ title: 'Приём ёжика' }))
    expect(text).toContain('прием ежика')
  })

  it('срок действия показывается как день, месяц, год', () => {
    const text = documentSearchText(doc({ expires_at: '2026-09-23' }))
    expect(text).toContain('23.09.2026')
  })

  it('срок без даты в строку не попадает', () => {
    const text = documentSearchText(doc({ expires_at: 'некогда' }))
    expect(text).not.toContain('некогда')
  })

  it('заметка и вид документа попадают в строку', () => {
    const text = documentSearchText(doc({ note: 'Лапа', category: 'vaccination' }))
    expect(text).toContain('лапа')
    expect(text).toContain('прививки')
  })

  it('из записей медкарты берутся причина, диагноз, клиника и день', () => {
    const text = documentSearchText(
      doc({
        medical_records: [{ id: 'r1', title: 'Первичный приём', diagnosis: 'Артрит', clinic: 'ВетДок', date: '2026-03-04' }],
      }),
    )
    expect(text).toContain('первичный прием')
    expect(text).toContain('артрит')
    expect(text).toContain('ветдок')
    expect(text).toContain('04.03.2026')
  })
})

describe('matchesDocumentQuery', () => {
  it('пустой запрос подходит всему', () => {
    expect(matchesDocumentQuery(doc(), '')).toBe(true)
    expect(matchesDocumentQuery(doc(), '   ')).toBe(true)
  })

  it('слово из названия находит', () => {
    expect(matchesDocumentQuery(doc(), 'рентген')).toBe(true)
  })

  it('слово из записи медкарты находит', () => {
    const d = doc({ medical_records: [{ id: 'r1', title: 'Осмотр', clinic: 'ВетДок' }] })
    expect(matchesDocumentQuery(d, 'ветдок')).toBe(true)
  })

  it('все слова запроса должны найтись', () => {
    expect(matchesDocumentQuery(doc(), 'рентген ортовет')).toBe(false)
  })

  it('незнакомое слово не подходит', () => {
    expect(matchesDocumentQuery(doc(), 'лодка')).toBe(false)
  })

  it('поиск не различает регистр', () => {
    expect(matchesDocumentQuery(doc(), 'РЕНТГЕН')).toBe(true)
  })

  it('поиск не различает ё и е', () => {
    expect(matchesDocumentQuery(doc({ title: 'Приём' }), 'прием')).toBe(true)
  })
})
