import { beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { installEnterKey } from '../../src/utils/enterKey'

/** Экран с полями и кнопкой: то, что видит человек. */
function screen(inner: string): void {
  document.body.innerHTML = `<main>${inner}</main>`
}

function field(id: string): HTMLInputElement {
  const el = document.getElementById(id) as HTMLInputElement
  if (!el) throw new Error(`поля ${id} нет`)
  return el
}

/** Нажатие Enter на поле. */
function pressEnter(el: HTMLElement): KeyboardEvent {
  const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
  el.dispatchEvent(event)
  return event
}

beforeAll(() => {
  // В jsdom у элементов нет размера, а без него поле считается невидимым
  HTMLElement.prototype.getClientRects = function () {
    return [{ width: 10, height: 10, top: 0, left: 0, right: 10, bottom: 10, x: 0, y: 0 }] as unknown as DOMRectList
  }
  installEnterKey()
})

beforeEach(() => {
  document.body.innerHTML = ''
})

describe('переход по Enter', () => {
  it('Enter на первом поле переносит на второе', () => {
    screen('<input id="a" /><input id="b" />')
    const a = field('a')
    a.focus()
    const event = pressEnter(a)
    expect(document.activeElement).toBe(field('b'))
    expect(event.defaultPrevented).toBe(true)
  })

  it('выключенное поле пропускается', () => {
    screen('<input id="a" /><input id="b" disabled /><input id="c" />')
    const a = field('a')
    a.focus()
    pressEnter(a)
    expect(document.activeElement).toBe(field('c'))
  })

  it('Enter на последнем поле без кнопки убирает фокус и закрывает клавиатуру', () => {
    screen('<input id="a" />')
    const a = field('a')
    a.focus()
    const event = pressEnter(a)
    expect(document.activeElement).toBe(document.body)
    expect(event.defaultPrevented).toBe(true)
  })

  it('Enter на последнем поле нажимает отмеченную кнопку', () => {
    screen('<input id="a" /><button data-enter-submit>Войти</button>')
    const a = field('a')
    let pressed = 0
    document.querySelector('button')!.addEventListener('click', () => {
      pressed += 1
    })
    a.focus()
    pressEnter(a)
    expect(pressed).toBe(1)
  })

  it('кнопка вне формы, но на том же экране, тоже нажимается', () => {
    screen('<form><input id="a" /></form><button data-enter-submit>Войти</button>')
    const a = field('a')
    let pressed = 0
    document.querySelector('button')!.addEventListener('click', () => {
      pressed += 1
    })
    a.focus()
    pressEnter(a)
    expect(pressed).toBe(1)
  })

  it('кнопка на другом экране не нажимается', () => {
    document.body.innerHTML = '<main><input id="a" /></main><footer><button data-enter-submit>Войти</button></footer>'
    const a = field('a')
    let pressed = 0
    document.querySelector('button')!.addEventListener('click', () => {
      pressed += 1
    })
    a.focus()
    pressEnter(a)
    expect(pressed).toBe(0)
    expect(document.activeElement).toBe(document.body)
  })

  it('в диалоге нажимается кнопка диалога, а не экрана', () => {
    screen('<button data-enter-submit>Сохранить</button><div role="dialog"><input id="a" /><button data-enter-submit>Отмена</button></div>')
    const a = field('a')
    const pressed: string[] = []
    for (const button of document.querySelectorAll('button')) {
      button.addEventListener('click', () => pressed.push(button.textContent ?? ''))
    }
    a.focus()
    pressEnter(a)
    expect(pressed).toEqual(['Отмена'])
  })

  it('выключенная кнопка не обещает перехода подсказкой', () => {
    // The hint must not promise a step that Enter will not take.
    screen('<input id="a" /><button data-enter-submit disabled>Войти</button>')
    const a = field('a')
    a.focus()
    pressEnter(a)
    expect(a.getAttribute('enterkeyhint')).toBe('done')
  })

  it('выключенная кнопка не нажимается', () => {
    screen('<input id="a" /><button data-enter-submit disabled>Войти</button>')
    const a = field('a')
    let pressed = 0
    document.querySelector('button')!.addEventListener('click', () => {
      pressed += 1
    })
    a.focus()
    pressEnter(a)
    expect(pressed).toBe(0)
  })
})

describe('поля, которых Enter не касается', () => {
  it('многострочное поле оставляет Enter для новой строки', () => {
    screen('<textarea id="t"></textarea>')
    const t = document.getElementById('t') as HTMLTextAreaElement
    t.focus()
    const event = pressEnter(t)
    expect(event.defaultPrevented).toBe(false)
    expect(document.activeElement).toBe(t)
  })

  it('поле со своей подсказкой остаётся в покое', () => {
    screen('<input id="a" enterkeyhint="done" /><input id="b" />')
    const a = field('a')
    a.focus()
    const event = pressEnter(a)
    expect(event.defaultPrevented).toBe(false)
    expect(document.activeElement).toBe(a)
  })

  it('флажок и радио не перехватывают Enter', () => {
    screen('<input id="c" type="checkbox" /><input id="r" type="radio" />')
    const c = field('c')
    c.focus()
    const event = pressEnter(c)
    expect(event.defaultPrevented).toBe(false)
  })
})

describe('подсказка на клавише', () => {
  it('на поле, за которым есть ещё одно, стоит «Далее»', () => {
    screen('<input id="a" /><input id="b" />')
    const a = field('a')
    a.focus()
    expect(a.getAttribute('enterkeyhint')).toBe('next')
  })

  it('на последнем поле с кнопкой стоит «Перейти»', () => {
    screen('<input id="a" /><button data-enter-submit>Войти</button>')
    const a = field('a')
    a.focus()
    expect(a.getAttribute('enterkeyhint')).toBe('go')
  })

  it('на последнем поле без кнопки стоит «Готово»', () => {
    screen('<input id="a" />')
    const a = field('a')
    a.focus()
    expect(a.getAttribute('enterkeyhint')).toBe('done')
  })

  it('на поле с чужой подсказкой своя не ставится', () => {
    screen('<input id="a" enterkeyhint="send" />')
    const a = field('a')
    a.focus()
    expect(a.getAttribute('enterkeyhint')).toBe('send')
  })
})
