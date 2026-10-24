import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FormChoiceSheet } from '../../src/components/FormChoiceSheet'

const options = [
  { value: 'Таблетка', label: 'Таблетка' },
  { value: 'Сироп', label: 'Сироп' },
  { value: '__other__', label: 'Другое' },
]

afterEach(cleanup)

describe('лист выбора из фиксированного списка', () => {
  it('нажатие на строку выбирает её, без кнопки «Готово»', () => {
    const onSelect = vi.fn()
    render(<FormChoiceSheet visible title="Форма выпуска" options={options} value="Таблетка" onClose={() => undefined} onSelect={onSelect} />)
    expect(screen.queryByText('Готово')).toBeNull()
    fireEvent.click(screen.getByText('Сироп'))
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onSelect).toHaveBeenCalledWith('Сироп')
  })

  it('выбранная строка помечена, остальные нет', () => {
    render(<FormChoiceSheet visible title="Форма выпуска" options={options} value="Сироп" onClose={() => undefined} onSelect={() => undefined} />)
    expect(screen.getByText('Сироп').closest('button')?.getAttribute('aria-current')).toBe('true')
    expect(screen.getByText('Таблетка').closest('button')?.getAttribute('aria-current')).toBeNull()
  })

  it('ничего не выбрано, пока не нажали', () => {
    const onSelect = vi.fn()
    render(<FormChoiceSheet visible title="Форма выпуска" options={options} onClose={() => undefined} onSelect={onSelect} />)
    expect(onSelect).not.toHaveBeenCalled()
  })
})
