import { describe, expect, it } from 'vitest'
import { isPublicPage } from '../../src/utils/publicPages'

describe('isPublicPage', () => {
  it('страница входа публична', () => {
    expect(isPublicPage('/login')).toBe(true)
  })

  it('страница регистрации публична', () => {
    expect(isPublicPage('/register')).toBe(true)
  })

  it('главная не публична', () => {
    expect(isPublicPage('/')).toBe(false)
  })

  it('список питомцев не публичен', () => {
    expect(isPublicPage('/pets/p1')).toBe(false)
  })

  it('медкарта по ссылке публична', () => {
    expect(isPublicPage('/share/medical/abc123')).toBe(true)
  })

  it('общая ссылка без адреса не публична', () => {
    expect(isPublicPage('/share/medical')).toBe(false)
  })
})
