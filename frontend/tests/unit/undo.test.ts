import { beforeEach, describe, expect, it, vi } from 'vitest'
import { closeSnackbar, getSnackbar, runSnackbarAction } from '../../src/utils/snackbar'
import { showUndo } from '../../src/utils/undo'

describe('showUndo', () => {
  beforeEach(() => {
    const current = getSnackbar()
    if (current) closeSnackbar(current.id)
  })

  it('полоса говорит, что случилось', () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn() })
    expect(getSnackbar()?.message).toBe('Отметка снята')
  })

  it('на полосе есть кнопка отмены', () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn() })
    expect(getSnackbar()?.action?.label).toBe('Отменить')
  })

  it('отмена выполняет действие', async () => {
    const onUndo = vi.fn()
    showUndo({ message: 'Отметка снята', onUndo })
    await runSnackbarAction(getSnackbar()!.id)
    expect(onUndo).toHaveBeenCalled()
  })

  it('после отмены говорит, что отменено', async () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn() })
    await runSnackbarAction(getSnackbar()!.id)
    expect(getSnackbar()?.message).toBe('Отменено')
  })

  it('неудачная отмена говорит, что отменить не вышло', async () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn().mockRejectedValue(new Error('сервер не ответил')) })
    await runSnackbarAction(getSnackbar()!.id)
    expect(getSnackbar()?.message).toBe('Не удалось отменить')
  })

  it('время на полосе можно задать своё', () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn(), duration: 1000 })
    expect(getSnackbar()?.duration).toBe(1000)
  })

  it('без своего времени полоса живёт столько, сколько полагается', () => {
    showUndo({ message: 'Отметка снята', onUndo: vi.fn() })
    expect(getSnackbar()?.duration).toBeUndefined()
  })
})
