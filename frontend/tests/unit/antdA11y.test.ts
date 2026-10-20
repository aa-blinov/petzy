import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { installAntdA11y } from '../../src/utils/antdA11y'

/** Кадр браузера: правки разметки доходят до страницы в следующем кадре */
async function tick(): Promise<void> {
  await new Promise((resolve) => requestAnimationFrame(() => resolve()))
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function add(html: string): HTMLElement {
  const host = document.createElement('div')
  host.innerHTML = html
  const first = host.firstElementChild as HTMLElement
  document.body.appendChild(first)
  return first
}

// Правки разметки навешиваются один раз, иначе обработчик клика сработает несколько раз
beforeAll(() => {
  const root = document.createElement('div')
  root.id = 'root'
  document.body.appendChild(root)
  // В jsdom у элементов нет размеров, а без них открытый слой не считается видимым
  Element.prototype.getClientRects = () => [{ width: 10, height: 10 }] as unknown as DOMRectList
  installAntdA11y()
})

beforeEach(() => {
  const root = document.getElementById('root')!
  root.innerHTML = ''
  for (const el of Array.from(document.body.children)) {
    if (el !== root) el.remove()
  }
  document.dispatchEvent(new Event('pointerdown'))
})

describe('строки списка', () => {
  it('строка становится кнопкой для экранного диктора', async () => {
    const row = add('<a class="adm-list-item">Рекс</a>')
    await tick()
    expect(row.getAttribute('role')).toBe('button')
    expect(row.getAttribute('tabindex')).toBe('0')
  })

  it('выключенная строка не входит в порядок обхода', async () => {
    const row = add('<a class="adm-list-item adm-list-item-disabled">Рекс</a>')
    await tick()
    expect(row.getAttribute('tabindex')).toBe('-1')
    expect(row.getAttribute('aria-disabled')).toBe('true')
  })

  it('строка с текстовым полем кнопкой не становится', async () => {
    const row = add('<div class="adm-form-item"><a class="adm-list-item"><input name="note" /></a></div>')
    await tick()
    expect(row.querySelector('.adm-list-item')?.hasAttribute('role')).toBe(false)
  })

  it('поле для чтения не становится второй остановкой', async () => {
    const row = add('<a class="adm-list-item"><input name="date" readonly /></a>')
    await tick()
    expect(row.querySelector('input')?.getAttribute('tabindex')).toBe('-1')
    expect(row.getAttribute('role')).toBe('button')
  })

  it('Enter нажимает строку', async () => {
    const onClick = vi.fn()
    const row = add('<a class="adm-list-item">Рекс</a>')
    row.addEventListener('click', onClick)
    await tick()
    row.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    expect(onClick).toHaveBeenCalled()
  })

  it('пробел нажимает строку и не прокручивает страницу', async () => {
    const onClick = vi.fn()
    const row = add('<a class="adm-list-item">Рекс</a>')
    row.addEventListener('click', onClick)
    await tick()
    const event = new KeyboardEvent('keydown', { key: ' ', bubbles: true, cancelable: true })
    row.dispatchEvent(event)
    expect(onClick).toHaveBeenCalled()
    expect(event.defaultPrevented).toBe(true)
  })

  it('выключенная строка не нажимается', async () => {
    const onClick = vi.fn()
    const row = add('<a class="adm-list-item adm-list-item-disabled">Рекс</a>')
    row.addEventListener('click', onClick)
    await tick()
    row.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
    expect(onClick).not.toHaveBeenCalled()
  })
})

describe('подписи полей', () => {
  it('подпись привязана к своему полю', async () => {
    add('<div class="adm-form-item"><label class="adm-form-item-label">Имя</label><input name="name" /></div>')
    await tick()
    const input = document.querySelector('input[name="name"]') as HTMLInputElement
    const label = document.querySelector('label') as HTMLLabelElement
    expect(input.id).toBeTruthy()
    expect(label.htmlFor).toBe(input.id)
  })

  it('обязательное поле помечено для диктора', async () => {
    add(
      '<div class="adm-form-item"><label class="adm-form-item-label">Имя <span class="adm-form-item-required-asterisk">*</span></label><input name="name" /></div>',
    )
    await tick()
    expect(document.querySelector('input[name="name"]')?.getAttribute('aria-required')).toBe('true')
  })

  it('необязательное поле не помечено', async () => {
    add('<div class="adm-form-item"><label class="adm-form-item-label">Имя</label><input name="name" /></div>')
    await tick()
    expect(document.querySelector('input[name="name"]')?.hasAttribute('aria-required')).toBe(false)
  })
})

describe('кнопка очистки', () => {
  it('становится кнопкой, но не лишней остановкой', async () => {
    const clear = add('<div class="adm-input-clear">×</div>')
    await tick()
    expect(clear.getAttribute('role')).toBe('button')
    expect(clear.getAttribute('tabindex')).toBe('-1')
  })
})

describe('меню действий', () => {
  it('отмена перестаёт быть пунктом списка', async () => {
    add(
      '<div class="adm-action-sheet-popup"><div class="adm-popup-body"><div class="adm-action-sheet-cancel" role="option" aria-label="Отмена"><button>Отмена</button></div></div></div>',
    )
    await tick()
    const cancel = document.querySelector('.adm-action-sheet-cancel') as HTMLElement
    expect(cancel.hasAttribute('role')).toBe(false)
    expect(cancel.hasAttribute('aria-label')).toBe(false)
  })

  it('тело меню называется диалогом', async () => {
    add(
      '<div class="adm-action-sheet-popup"><div class="adm-popup-body"><div class="adm-action-sheet-cancel" role="option"><button>Отмена</button></div></div></div>',
    )
    await tick()
    const body = document.querySelector('.adm-popup-body') as HTMLElement
    expect(body.getAttribute('role')).toBe('dialog')
    expect(body.getAttribute('aria-label')).toBe('Действия')
  })
})

describe('открытый слой', () => {
  it('страница за слоем прячется от диктора', async () => {
    document.getElementById('root')!.innerHTML = '<button id="opener">Открыть</button>'
    add('<div class="adm-popup"><button id="inside">Хорошо</button></div>')
    await tick()
    expect(document.getElementById('root')?.getAttribute('aria-hidden')).toBe('true')
  })

  it('после закрытия страница снова видна', async () => {
    document.getElementById('root')!.innerHTML = '<button id="opener">Открыть</button>'
    const popup = add('<div class="adm-popup"><button id="inside">Хорошо</button></div>')
    await tick()
    popup.remove()
    await tick()
    expect(document.getElementById('root')?.hasAttribute('aria-hidden')).toBe(false)
  })

  it('фокус возвращается на то, что открыло слой', async () => {
    const opener = document.createElement('button')
    opener.id = 'opener'
    document.getElementById('root')!.appendChild(opener)
    opener.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true }))
    const popup = add('<div class="adm-popup"><button id="inside">Хорошо</button></div>')
    await tick()
    popup.remove()
    await tick()
    expect(document.activeElement).toBe(opener)
  })

  it('Tab не уходит из слоя', async () => {
    document.getElementById('root')!.innerHTML = '<button id="outside">Вне</button>'
    add('<div class="adm-popup"><button id="inside">Хорошо</button></div>')
    await tick()
    document.getElementById('outside')?.focus()
    const event = new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true })
    document.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
    expect(document.activeElement).toBe(document.getElementById('inside'))
  })
})
