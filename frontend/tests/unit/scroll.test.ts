import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { jumpToTop, prefersReducedMotion, restorePosition, savePosition, savedPosition, scrollToTop } from '../../src/utils/scroll'

// Позиции лежат в хранилище вкладки, а Node держит своё пустое и затеняет им страницу,
// поэтому сначала берём хранилище страницы
beforeAll(() => {
  const jsdomStorage = (window as unknown as { _sessionStorage?: Storage })._sessionStorage
  Object.defineProperty(window, 'sessionStorage', { value: jsdomStorage, configurable: true, writable: true })
})

/** Один кадр: прокрутка ждёт следующего. */
function frame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

/** Высота страницы, до которой можно докрутить. */
function setPageHeight(px: number) {
  Object.defineProperty(document.documentElement, 'scrollHeight', { value: px, configurable: true })
}

beforeEach(() => {
  sessionStorage.clear()
  setPageHeight(5000)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('запомненная позиция экрана', () => {
  it('позиция возвращается на своём экране', () => {
    savePosition('k1', 320, '/pets')
    expect(savedPosition('k1', '/pets')).toBe(320)
  })

  it('дробная позиция округляется до целого', () => {
    savePosition('k1', 320.6, '/pets')
    expect(savedPosition('k1', '/pets')).toBe(321)
  })

  it('другой экран не наследует чужую позицию', () => {
    savePosition('k1', 320, '/pets')
    expect(savedPosition('k1', '/medications')).toBeNull()
  })

  it('позиция в самом верху не восстанавливается', () => {
    savePosition('k1', 0, '/pets')
    expect(savedPosition('k1', '/pets')).toBeNull()
  })

  it('неизвестный ключ не даёт позиции', () => {
    expect(savedPosition('нет-такого', '/pets')).toBeNull()
  })

  it('самая старая позиция забывается, когда их становится больше шестидесяти', () => {
    for (let i = 1; i <= 61; i++) savePosition(`k${i}`, i, '/pets')
    expect(savedPosition('k1', '/pets')).toBeNull()
    expect(savedPosition('k61', '/pets')).toBe(61)
  })

  it('приватный режим не ломает страницу', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('private mode')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('private mode')
    })
    expect(() => savePosition('k1', 320, '/pets')).not.toThrow()
    expect(savedPosition('k1', '/pets')).toBeNull()
  })
})

describe('прокрутка наверх', () => {
  it('кнопка наверх всегда прокручивает без анимации', () => {
    jumpToTop()
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
  })

  it('повторное нажатие на свой tab прокручивает плавно', () => {
    scrollToTop()
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'smooth' })
  })

  it('при отключённой анимации прокрутка идёт без неё', () => {
    window.matchMedia = ((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia
    expect(prefersReducedMotion()).toBe(true)
    scrollToTop()
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' })
  })
})

describe('возврат на прежнее место', () => {
  it('страница прокручивается туда, где человек остановился', async () => {
    restorePosition(1000)
    await frame()
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 1000, left: 0, behavior: 'instant' })
  })

  it('своя прокрутка человека отменяет возврат', async () => {
    restorePosition(1000)
    window.dispatchEvent(new WheelEvent('wheel'))
    await frame()
    expect(window.scrollTo).not.toHaveBeenCalled()
  })

  it('если страница так и не выросла, прокрутка остаётся на месте', () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'Date', 'performance', 'requestAnimationFrame', 'cancelAnimationFrame'] })
    setPageHeight(800)
    restorePosition(1000)
    vi.advanceTimersByTime(3000)
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 32, left: 0, behavior: 'instant' })
  })
})
