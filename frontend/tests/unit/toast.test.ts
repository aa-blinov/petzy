import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { showToast } from '../../src/utils/toast'
import { closeSnackbar, getSnackbar } from '../../src/utils/snackbar'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  const current = getSnackbar()
  if (current) closeSnackbar(current.id)
  vi.useRealTimers()
})

describe('обычные сообщения', () => {
  it('подтверждение приходит как подтверждение', () => {
    showToast.success('Запись сохранена')
    expect(getSnackbar()?.tone).toBe('success')
  })

  it('ошибка приходит как ошибка', () => {
    showToast.failure('Не получилось сохранить')
    expect(getSnackbar()?.tone).toBe('error')
  })

  it('обычное сообщение приходит как обычное', () => {
    showToast.info('Данные обновлены')
    expect(getSnackbar()?.tone).toBe('info')
  })

  it('после сообщения вызывается подведённый обработчик', () => {
    const afterClose = vi.fn()
    showToast.success('Запись сохранена', { afterClose })
    vi.advanceTimersByTime(3000)
    expect(afterClose).toHaveBeenCalledWith('timeout')
  })

  it('ошибка держится дольше подтверждения', () => {
    showToast.failure('Не получилось сохранить')
    vi.advanceTimersByTime(3000)
    expect(getSnackbar()).not.toBeNull()
    vi.advanceTimersByTime(2000)
    expect(getSnackbar()).toBeNull()
  })

  it('своя длительность действует', () => {
    showToast.success('Готово', { duration: 1000 })
    vi.advanceTimersByTime(1000)
    expect(getSnackbar()).toBeNull()
  })
})

describe('сообщение о загрузке', () => {
  it('загрузка не занимает нижнюю полосу', () => {
    const handle = showToast.loading('Сохраняю')
    expect(getSnackbar()).toBeNull()
    handle.close()
  })

  it('текст загрузки виден на странице', async () => {
    // Спиннер antd-mobile рисуется React'ом, и тот рисунок приходит на следующем такте
    vi.useRealTimers()
    const handle = showToast.loading('Сохраняю')
    let seen = false
    for (let i = 0; i < 50 && !seen; i++) {
      await new Promise((resolve) => setTimeout(resolve, 20))
      seen = document.body.textContent?.includes('Сохраняю') ?? false
    }
    expect(seen).toBe(true)
    handle.close()
  })
})
