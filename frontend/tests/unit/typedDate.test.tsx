import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { Form } from 'antd-mobile'
import { useState } from 'react'
import { DatePickerField } from '../../src/components/DatePickerField'
import { useTypedDateProblems } from '../../src/hooks/useTypedDateProblems'
import { INCOMPLETE_DATE, readTypedDate } from '../../src/utils/typedDate'
import { weightOfDay } from '../../src/utils/visitWeight'

afterEach(() => cleanup())

const today = new Date(2026, 9, 24)

describe('readTypedDate', () => {
  const past = { today, yearsBack: 30, yearsForward: 0 }
  const future = { today, yearsBack: 0, yearsForward: 10 }

  it('принимает настоящую дату', () => {
    expect(readTypedDate('17082025', past)).toEqual({ iso: '2025-08-17', error: '' })
  })

  it('пустой текст не ошибка', () => {
    expect(readTypedDate('', past)).toEqual({ iso: null, error: '' })
  })

  it('недописанная дата это ошибка, а не пропуск', () => {
    expect(readTypedDate('12.1', past).error).toBe(INCOMPLETE_DATE)
  })

  it('несуществующая дата названа', () => {
    expect(readTypedDate('31022026', past).error).toContain('Такой даты нет')
  })

  it('будущее для записи названо будущим', () => {
    expect(readTypedDate('01012027', past).error).toBe('Дата не может быть в будущем')
  })

  it('прошлое для повтора названо прошедшим', () => {
    expect(readTypedDate('01012026', future).error).toBe('Дата уже прошла')
  })

  it('слишком давний год называет границу', () => {
    expect(readTypedDate('01011980', past).error).toBe('Год не раньше 1996')
  })

  it('слишком далёкий год называет границу', () => {
    expect(readTypedDate('01012040', future).error).toBe('Год не позже 2036')
  })
})

describe('useTypedDateProblems', () => {
  it('отказывает в сохранении, пока в поле неверная дата, и разрешает, когда её нет', () => {
    const { result } = renderHook(() => useTypedDateProblems())
    expect(result.current.blocked).toBe(false)
    act(() => result.current.report('date')('Дата уже прошла'))
    expect(result.current.blocked).toBe(true)
    let refused = false
    act(() => {
      refused = result.current.refuse()
    })
    expect(refused).toBe(true)
    expect(result.current.refusals).toBe(1)
    act(() => result.current.report('date')(''))
    expect(result.current.blocked).toBe(false)
  })
})

describe('weightOfDay', () => {
  const series = [
    { date: '2026-10-20', value: 4.65 },
    { date: '2026-10-20', value: 6.6 },
    { date: '2026-10-21', value: 7 },
  ]
  it('берёт последний замер дня и считает замеры', () => {
    expect(weightOfDay(series, '2026-10-20')).toEqual({ value: 6.6, count: 2 })
  })
  it('без замера в этот день ничего', () => {
    expect(weightOfDay(series, '2026-10-22')).toBeUndefined()
    expect(weightOfDay(undefined, '2026-10-22')).toBeUndefined()
  })
})

function Harness({ onProblem }: { onProblem: (m: string) => void }) {
  const [value, setValue] = useState('2026-10-01')
  return (
    <Form>
      <DatePickerField label="Начало" value={value} onChange={setValue} yearsBack={5} yearsForward={1} onTypedProblem={onProblem} />
      <output data-testid="value">{value}</output>
    </Form>
  )
}

describe('DatePickerField: введённая цифрами дата', () => {
  const open = () => {
    fireEvent.click(screen.getByText('Ввести цифрами'))
    return screen.getAllByLabelText('Начало, цифрами').find((el) => el.tagName === 'INPUT') as HTMLInputElement
  }

  it('несуществующая дата сообщается форме и не меняет значение', () => {
    const onProblem = vi.fn()
    render(<Harness onProblem={onProblem} />)
    fireEvent.change(open(), { target: { value: '31022026' } })
    expect(onProblem).toHaveBeenLastCalledWith(expect.stringContaining('Такой даты нет'))
    expect(screen.getByTestId('value').textContent).toBe('2026-10-01')
  })

  it('недописанная дата сообщается форме', () => {
    const onProblem = vi.fn()
    render(<Harness onProblem={onProblem} />)
    fireEvent.change(open(), { target: { value: '121' } })
    expect(onProblem).toHaveBeenLastCalledWith(INCOMPLETE_DATE)
  })

  it('верная дата принимается и проблема снимается', () => {
    const onProblem = vi.fn()
    render(<Harness onProblem={onProblem} />)
    const input = open()
    fireEvent.change(input, { target: { value: '12' } })
    fireEvent.change(input, { target: { value: '15112026' } })
    expect(screen.getByTestId('value').textContent).toBe('2026-11-15')
    expect(onProblem).toHaveBeenLastCalledWith('')
  })

  it('закрытие ввода цифрами снимает проблему', () => {
    const onProblem = vi.fn()
    render(<Harness onProblem={onProblem} />)
    fireEvent.change(open(), { target: { value: '12' } })
    fireEvent.click(screen.getByText('Ввести цифрами'))
    expect(onProblem).toHaveBeenLastCalledWith('')
  })
})
