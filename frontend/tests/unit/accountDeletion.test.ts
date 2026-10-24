import { describe, expect, it } from 'vitest'
import { deletionSummary } from '../../src/utils/accountDeletion'

const pet = (name: string) => ({ id: name, name })

describe('что сказано при удалении аккаунта', () => {
  it('без питомцев не говорит про «ничьих питомцев»', () => {
    expect(deletionSummary({ deleted: [], transferred: [], left: [] })).toBe('')
  })

  it('один питомец стоит в единственном числе', () => {
    expect(deletionSummary({ deleted: [pet('Рекс')], transferred: [], left: [] })).toBe(
      'Удалится: «Рекс», вместе с записями, лекарствами и документами.',
    )
  })

  it('несколько питомцев и чужие питомцы со своими падежами', () => {
    expect(deletionSummary({ deleted: [pet('А'), pet('Б')], transferred: [pet('В')], left: [pet('Г'), pet('Д')] })).toBe(
      'Удалятся: «А», «Б», вместе с записями, лекарствами и документами. Перейдёт другому: «В». Пропадёт доступ к 2 питомцам других людей.',
    )
  })

  it('доступ к одному питомцу других людей', () => {
    expect(deletionSummary({ deleted: [], transferred: [], left: [pet('Г')] })).toBe('Пропадёт доступ к 1 питомцу других людей.')
  })
})
