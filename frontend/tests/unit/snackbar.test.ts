import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  closeSnackbar,
  getSnackbar,
  runSnackbarAction,
  showSnackbar,
  subscribeSnackbar,
  updateSnackbar,
} from '../../src/utils/snackbar'

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  const current = getSnackbar()
  if (current) closeSnackbar(current.id)
  vi.useRealTimers()
})

describe('сколько живёт сообщение', () => {
  it('подтверждение держится три секунды', () => {
    const onDismiss = vi.fn()
    showSnackbar({ message: 'Запись сохранена', tone: 'success', onDismiss })
    vi.advanceTimersByTime(2999)
    expect(getSnackbar()).not.toBeNull()
    vi.advanceTimersByTime(1)
    expect(getSnackbar()).toBeNull()
    expect(onDismiss).toHaveBeenCalledWith('timeout')
  })

  it('ошибка держится пять секунд, её надо успеть прочитать', () => {
    showSnackbar({ message: 'Не получилось сохранить', tone: 'error' })
    vi.advanceTimersByTime(4999)
    expect(getSnackbar()).not.toBeNull()
    vi.advanceTimersByTime(1)
    expect(getSnackbar()).toBeNull()
  })

  it('сообщение с действием держится шесть секунд', () => {
    showSnackbar({ message: 'Удалено', tone: 'info', action: { label: 'Отменить', run: () => {} } })
    vi.advanceTimersByTime(5999)
    expect(getSnackbar()).not.toBeNull()
    vi.advanceTimersByTime(1)
    expect(getSnackbar()).toBeNull()
  })

  it('своя длительность важнее умолчания', () => {
    showSnackbar({ message: 'Коротко', tone: 'error', duration: 1000 })
    vi.advanceTimersByTime(1000)
    expect(getSnackbar()).toBeNull()
  })

  it('сообщение без тона считается обычным', () => {
    showSnackbar({ message: 'Готово' })
    expect(getSnackbar()?.tone).toBe('info')
  })
})

describe('одно сообщение за раз', () => {
  it('новое сообщение вытесняет прежнее', () => {
    const onDismiss = vi.fn()
    showSnackbar({ message: 'Первое', onDismiss })
    showSnackbar({ message: 'Второе' })
    expect(onDismiss).toHaveBeenCalledWith('replaced')
    expect(getSnackbar()?.message).toBe('Второе')
  })

  it('вытесненное сообщение не снимает новое по своему таймеру', () => {
    showSnackbar({ message: 'Первое' })
    showSnackbar({ message: 'Второе' })
    vi.advanceTimersByTime(3000)
    expect(getSnackbar()).toBeNull()
  })
})

describe('действие в сообщении', () => {
  it('успешное действие закрывает сообщение', async () => {
    const onDismiss = vi.fn()
    const run = vi.fn()
    showSnackbar({ message: 'Удалено', action: { label: 'Отменить', run }, onDismiss })
    const id = getSnackbar()!.id
    const done = await runSnackbarAction(id)
    expect(done).toBe(true)
    expect(run).toHaveBeenCalled()
    expect(getSnackbar()).toBeNull()
    expect(onDismiss).toHaveBeenCalledWith('action')
  })

  it('неудачное действие оставляет сообщение на экране', async () => {
    const onDismiss = vi.fn()
    showSnackbar({
      message: 'Удалено',
      action: {
        label: 'Отменить',
        run: () => {
          throw new Error('не получилось')
        },
      },
      onDismiss,
    })
    const id = getSnackbar()!.id
    const done = await runSnackbarAction(id)
    expect(done).toBe(false)
    expect(getSnackbar()).not.toBeNull()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('после неудачного действия сообщение всё же исчезает', async () => {
    showSnackbar({
      message: 'Удалено',
      duration: 3000,
      action: {
        label: 'Отменить',
        run: () => {
          throw new Error('не получилось')
        },
      },
    })
    const id = getSnackbar()!.id
    await runSnackbarAction(id)
    vi.advanceTimersByTime(3000)
    expect(getSnackbar()).toBeNull()
  })

  it('у сообщения без действия нажатия действия нет', async () => {
    showSnackbar({ message: 'Готово' })
    const id = getSnackbar()!.id
    expect(await runSnackbarAction(id)).toBe(false)
    expect(getSnackbar()).not.toBeNull()
  })
})

describe('конец сообщения', () => {
  it('закрытие рукой снимает сообщение', () => {
    const onDismiss = vi.fn()
    const handle = showSnackbar({ message: 'Готово', onDismiss })
    handle.close()
    expect(getSnackbar()).toBeNull()
    expect(onDismiss).toHaveBeenCalledWith('closed')
  })

  it('изменение текста начинает отсчёт заново', () => {
    showSnackbar({ message: 'Сохраняю' })
    const id = getSnackbar()!.id
    vi.advanceTimersByTime(2000)
    updateSnackbar(id, { message: 'Сохранено' })
    expect(getSnackbar()?.message).toBe('Сохранено')
    vi.advanceTimersByTime(2000)
    expect(getSnackbar()).not.toBeNull()
    vi.advanceTimersByTime(1000)
    expect(getSnackbar()).toBeNull()
  })

  it('изменение закончившегося сообщения ничего не делает', () => {
    showSnackbar({ message: 'Сохраняю' })
    const id = getSnackbar()!.id
    vi.advanceTimersByTime(3000)
    expect(getSnackbar()).toBeNull()
    updateSnackbar(id, { message: 'Сохранено' })
    expect(getSnackbar()).toBeNull()
  })
})

describe('подписка на сообщения', () => {
  it('подписчик видит появление и исчезновение сообщения', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeSnackbar(listener)
    showSnackbar({ message: 'Готово' })
    expect(listener).toHaveBeenCalledTimes(1)
    vi.advanceTimersByTime(3000)
    expect(listener).toHaveBeenCalledTimes(2)
    unsubscribe()
  })

  it('отписавшийся подписчик больше ничего не видит', () => {
    const listener = vi.fn()
    subscribeSnackbar(listener)()
    showSnackbar({ message: 'Готово' })
    expect(listener).not.toHaveBeenCalled()
  })
})
