import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChoiceList } from '../../src/components/ChoiceSheetField'

afterEach(cleanup)

const OPTIONS = [
  { label: 'Прививки', value: 'vaccination' },
  { label: 'Анализы', value: 'lab_result' },
  { label: 'Другое', value: 'other' },
]

describe('список фиксированных вариантов', () => {
  it('нажатие на строку выбирает её', () => {
    const onPick = vi.fn()
    render(<ChoiceList options={OPTIONS} value="" onPick={onPick} />)
    fireEvent.click(screen.getByRole('option', { name: 'Анализы' }))
    expect(onPick).toHaveBeenCalledWith('lab_result')
  })

  it('отмечает выбранную строку и только её', () => {
    render(<ChoiceList options={OPTIONS} value="other" onPick={() => {}} />)
    const chosen = screen.getAllByRole('option').filter((o) => o.getAttribute('aria-selected') === 'true')
    expect(chosen.map((o) => o.textContent)).toEqual(['Другое'])
  })

  it('не содержит «Готово»: принять первый пункт молча нельзя', () => {
    render(<ChoiceList options={OPTIONS} value="" onPick={() => {}} />)
    expect(screen.queryByText('Готово')).toBeNull()
    expect(screen.getAllByRole('option')).toHaveLength(OPTIONS.length)
  })
})
