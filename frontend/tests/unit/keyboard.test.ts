import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { installKeyboardWatch } from '../../src/utils/keyboard'

/** То, что браузер сообщает о видимой части страницы. */
class FakeViewport extends EventTarget {
  offsetTop = 0
  height = 600
  scale = 1
}

const viewport = new FakeViewport()

function setInnerHeight(px: number) {
  Object.defineProperty(window, 'innerHeight', { value: px, configurable: true })
}

/** Страница с одним полем и одной кнопкой. */
function screen(): void {
  document.body.innerHTML = '<main><input id="a" /><button id="b">Кнопка</button></main>'
}

function refreshViewport() {
  viewport.dispatchEvent(new Event('resize'))
}

beforeAll(() => {
  Object.defineProperty(window, 'visualViewport', { value: viewport, configurable: true })
  setInnerHeight(800)
  installKeyboardWatch()
})

beforeEach(() => {
  viewport.offsetTop = 0
  viewport.height = 600
  viewport.scale = 1
  setInnerHeight(800)
  screen()
  refreshViewport()
})

describe('клавиатура на экране', () => {
  it('поле под клавиатурой сдвигает страницу', () => {
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    expect(document.documentElement.classList.contains('keyboard-open')).toBe(true)
    expect(document.documentElement.style.getPropertyValue('--keyboard-inset')).toBe('200px')
  })

  it('клавиатура в 120 пикселей и выше сдвигает страницу', () => {
    viewport.height = 680
    refreshViewport()
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    expect(document.documentElement.classList.contains('keyboard-open')).toBe(true)
  })

  it('клавиатура ниже 120 пикселей страницу не сдвигает', () => {
    viewport.height = 681
    refreshViewport()
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    expect(document.documentElement.classList.contains('keyboard-open')).toBe(false)
    expect(document.documentElement.style.getPropertyValue('--keyboard-inset')).toBe('0px')
  })

  it('фокус не на поле: клавиатура не считается открытой', () => {
    const button = document.getElementById('b') as HTMLButtonElement
    button.focus()
    expect(document.documentElement.classList.contains('keyboard-open')).toBe(false)
  })

  it('когда клавиатура ушла, страница возвращается на место', () => {
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    viewport.height = 800
    refreshViewport()
    expect(document.documentElement.classList.contains('keyboard-open')).toBe(false)
    expect(document.documentElement.style.getPropertyValue('--keyboard-inset')).toBe('0px')
  })

  it('нижние элементы поднимаются над клавиатурой', () => {
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    expect(document.documentElement.style.getPropertyValue('--keyboard-fixed-offset')).toBe('200px')
  })

  it('если страница сама уменьшилась, нижние элементы не поднимаются', () => {
    const input = document.getElementById('a') as HTMLInputElement
    input.focus()
    // Браузер, который сжимает страницу вместо того, чтобы накрывать её клавиатурой
    setInnerHeight(500)
    refreshViewport()
    expect(document.documentElement.style.getPropertyValue('--keyboard-inset')).toBe('200px')
    expect(document.documentElement.style.getPropertyValue('--keyboard-fixed-offset')).toBe('0px')
  })
})
