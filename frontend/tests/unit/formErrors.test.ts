import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { onInvalidSubmit } from '../../src/utils/formErrors'

/** Живая область, куда пишется сообщение для экранного диктора. */
function liveRegion(): HTMLElement {
  const el = document.querySelector<HTMLElement>('[aria-live="assertive"]')
  expect(el).toBeTruthy()
  return el!
}

/** Кадр браузера: сообщение и прокрутка случаются в нём. */
function frame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

function formItem(html: string): HTMLElement {
  const host = document.createElement('div')
  host.innerHTML = html
  const item = host.firstElementChild as HTMLElement
  document.body.appendChild(item)
  return item
}

describe('onInvalidSubmit', () => {
  beforeEach(() => {
    document.body.innerHTML = ''
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation((query: string) => ({ matches: false, media: query, addEventListener: () => {}, removeEventListener: () => {} })),
    )
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('одна ошибка говорит про одно поле', async () => {
    onInvalidSubmit({ name: { type: 'required', message: 'Укажите имя' } })
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте поле с ошибкой')
  })

  it('две ошибки говорят про два поля', async () => {
    onInvalidSubmit({
      name: { type: 'required', message: 'Укажите имя' },
      weight: { type: 'required', message: 'Укажите вес' },
    })
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте 2 поля с ошибками')
  })

  it('пять ошибок говорят про пять полей', async () => {
    onInvalidSubmit({
      a: { message: 'a' },
      b: { message: 'b' },
      c: { message: 'c' },
      d: { message: 'd' },
      e: { message: 'e' },
    })
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте 5 полей с ошибками')
  })

  it('ошибки внутри группы тоже считаются', async () => {
    onInvalidSubmit({
      group: {
        first: { message: 'первое' },
        second: { message: 'второе' },
      },
    })
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте 2 поля с ошибками')
  })

  it('ошибка без текста полем не считается', async () => {
    onInvalidSubmit({ name: { type: 'required' } })
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте поле с ошибкой')
  })

  it('без ошибок всё равно говорит про одно поле', async () => {
    onInvalidSubmit({})
    await frame()
    expect(liveRegion().textContent).toBe('Исправьте поле с ошибкой')
  })

  it('поле с первой ошибкой получает фокус', async () => {
    formItem(
      '<div class="adm-form-item"><input name="name" /><div class="field-error">Укажите имя</div></div>',
    )
    onInvalidSubmit({ name: { message: 'Укажите имя' } })
    await frame()
    expect(document.activeElement).toBe(document.querySelector('input[name="name"]'))
  })

  it('поле-элемент со своей ролью получает фокус сам', async () => {
    formItem('<div class="adm-form-item" role="button" tabindex="0"><div class="field-error">Укажите дату</div></div>')
    onInvalidSubmit({ date: { message: 'Укажите дату' } })
    await frame()
    expect(document.activeElement).toBe(document.querySelector('[role="button"]'))
  })

  it('страница прокручивается к ошибке', async () => {
    formItem('<div class="adm-form-item"><input name="name" /><div class="field-error">Укажите имя</div></div>')
    onInvalidSubmit({ name: { message: 'Укажите имя' } })
    await frame()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'center', behavior: 'smooth' })
  })

  it('при спокойном режиме прокрутка идёт без анимации', async () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockImplementation((query: string) => ({ matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {} })),
    )
    formItem('<div class="adm-form-item"><input name="name" /><div class="field-error">Укажите имя</div></div>')
    onInvalidSubmit({ name: { message: 'Укажите имя' } })
    await frame()
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'center', behavior: 'auto' })
  })

  it('без ошибки на странице ничего не ломается', async () => {
    onInvalidSubmit({ name: { message: 'Укажите имя' } })
    await frame()
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  })
})
