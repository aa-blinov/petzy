import { describe, expect, it } from 'vitest'
import { returnPath, returnState } from '../../src/utils/returnTo'

describe('returnState', () => {
  it('запоминает, куда шёл человек', () => {
    expect(returnState('/pets/p1')).toEqual({ from: '/pets/p1' })
  })

  it('на главной возвращаться некуда', () => {
    expect(returnState('/')).toBeUndefined()
  })

  it('на странице входа возвращаться некуда', () => {
    expect(returnState('/login')).toBeUndefined()
  })

  it('пустой адрес не запоминается', () => {
    expect(returnState('')).toBeUndefined()
  })
})

describe('returnPath', () => {
  it('отдаёт наш адрес', () => {
    expect(returnPath({ from: '/pets/p1' })).toBe('/pets/p1')
  })

  it('без адреса ведёт на главную', () => {
    expect(returnPath(null)).toBe('/')
    expect(returnPath(undefined)).toBe('/')
  })

  it('чужой сайт не ведёт туда', () => {
    expect(returnPath({ from: 'https://example.com' })).toBe('/')
  })

  it('адрес с двойным слэшем не ведёт наружу', () => {
    expect(returnPath({ from: '//example.com' })).toBe('/')
  })

  it('на страницу входа не возвращаются', () => {
    expect(returnPath({ from: '/login' })).toBe('/')
  })

  it('не адрес не принимается', () => {
    expect(returnPath({ from: 42 })).toBe('/')
  })
})
