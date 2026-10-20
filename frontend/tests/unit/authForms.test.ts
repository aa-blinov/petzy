import { act, createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { passwordProblem, retryAfterSeconds, retryNote, useRetryLock } from '../../src/utils/authForms'

// React спрашивает, идёт ли проверка через act, иначе ругается на обновления вне act
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function tooManyAttempts(retry_after: unknown): unknown {
  return { isAxiosError: true, response: { status: 429, data: { retry_after } } }
}

describe('passwordProblem', () => {
  it('пустой пароль не ошибка', () => {
    expect(passwordProblem('')).toBeNull()
  })

  it('короткий пароль отвергается', () => {
    expect(passwordProblem('коротк')).toBe('Не короче 8 символов')
  })

  it('пароль в восемь символов проходит', () => {
    expect(passwordProblem('password')).toBeNull()
  })

  it('пароль длиннее семидесяти двух байт отвергается', () => {
    expect(passwordProblem('ы'.repeat(35) + 'abcd')).toBe('Пароль слишком длинный')
  })

  it('ровно семьдесят два байта проходят', () => {
    expect(passwordProblem('ы'.repeat(34) + 'abcd')).toBeNull()
  })

  it('пароль, совпадающий с логином, отвергается', () => {
    expect(passwordProblem('Password1', 'password1')).toBe('Пароль не должен совпадать с логином')
  })

  it('совпадение с логином не зависит от регистра', () => {
    expect(passwordProblem('PASSWORD1', 'password1')).toBe('Пароль не должен совпадать с логином')
  })

  it('без логина совпадение не проверяется', () => {
    expect(passwordProblem('password1')).toBeNull()
  })

  it('пароль из двух букв отвергается', () => {
    expect(passwordProblem('aabbaabb')).toBe('Нужно хотя бы три разных символа')
  })

  it('пароль из трёх букв проходит', () => {
    expect(passwordProblem('aabbaacc')).toBeNull()
  })
})

describe('retryAfterSeconds', () => {
  it('берёт время из ответа сервера', () => {
    expect(retryAfterSeconds(tooManyAttempts(30))).toBe(30)
  })

  it('на другой ошибке ждать не надо', () => {
    expect(retryAfterSeconds({ isAxiosError: true, response: { status: 500, data: { retry_after: 30 } } })).toBe(0)
  })

  it('на не-axios ошибке ждать не надо', () => {
    expect(retryAfterSeconds(new Error('сбой'))).toBe(0)
  })

  it('без времени в ответе ждать не надо', () => {
    expect(retryAfterSeconds(tooManyAttempts(undefined))).toBe(0)
  })

  it('на нулевом времени ждать не надо', () => {
    expect(retryAfterSeconds(tooManyAttempts(0))).toBe(0)
  })

  it('на отрицательном времени ждать не надо', () => {
    expect(retryAfterSeconds(tooManyAttempts(-5))).toBe(0)
  })
})

describe('retryNote', () => {
  it('когда ждать не надо, подсказки нет', () => {
    expect(retryNote(0)).toBeNull()
  })

  it('на отрицательном времени подсказки нет', () => {
    expect(retryNote(-1)).toBeNull()
  })

  it('подсказка говорит, сколько ждать', () => {
    expect(retryNote(30)).toBe('Слишком много попыток с этого адреса. Повторите через 30 с')
  })
})

describe('useRetryLock', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  /** Хук показывается в разметке, чтобы состояние можно было прочитать */
  function mountHook(err: unknown) {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    function Probe() {
      const { left, lock } = useRetryLock()
      return createElement(
        'div',
        null,
        createElement('span', { id: 'left' }, String(left)),
        createElement('button', { id: 'lock', onClick: () => lock(err) }, 'запереть'),
      )
    }
    act(() => {
      root.render(createElement(Probe))
    })
    return {
      left: () => Number(container.querySelector('#left')?.textContent),
      lock: () => {
        act(() => {
          container.querySelector<HTMLButtonElement>('#lock')?.click()
        })
      },
    }
  }

  it('после отказа считает время, а потом открывает форму', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T10:00:00Z'))
    const hook = mountHook(tooManyAttempts(3))

    hook.lock()
    expect(hook.left()).toBe(3)

    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(hook.left()).toBe(2)

    act(() => {
      vi.advanceTimersByTime(2000)
    })
    expect(hook.left()).toBe(0)
  })

  it('ошибка без ограничения не запирает форму', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-01-01T10:00:00Z'))
    const hook = mountHook(new Error('сбой'))

    hook.lock()
    expect(hook.left()).toBe(0)
  })
})
