import { describe, expect, it } from 'vitest'
import { formatFileSize } from '../../src/utils/fileSize'

const MB = 1024 * 1024
const GB = 1024 * MB

describe('formatFileSize', () => {
  it('пустой файл не показывается нулём байт', () => {
    expect(formatFileSize(0)).toBe('1 КБ')
  })

  it('маленький файл округляется до килобайт', () => {
    expect(formatFileSize(840)).toBe('1 КБ')
  })

  it('сотня килобайт остаётся в килобайтах', () => {
    expect(formatFileSize(100 * 1024)).toBe('100 КБ')
  })

  it('мегабайты до десяти показываются с дробной частью', () => {
    expect(formatFileSize(4.5 * MB)).toBe('4,5 МБ')
  })

  it('мегабайты после десяти показываются целиком', () => {
    expect(formatFileSize(12.4 * MB)).toBe('12 МБ')
  })

  it('до гигабайта остаётся в мегабайтах', () => {
    expect(formatFileSize(900 * MB)).toBe('900 МБ')
  })

  it('гигабайты показываются с дробной частью', () => {
    expect(formatFileSize(1.2 * GB)).toBe('1,2 ГБ')
  })
})
