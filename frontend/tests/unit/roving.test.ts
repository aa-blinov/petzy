import { describe, expect, it } from 'vitest'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { rovingKeyDown, rovingTabIndex } from '../../src/utils/roving'

/** Группа радио на странице и то, какой из них нажали. */
function group(count = 3): { root: HTMLElement; clicked: number[] } {
  const root = document.createElement('div')
  const clicked: number[] = []
  for (let i = 0; i < count; i++) {
    const radio = document.createElement('button')
    radio.setAttribute('role', 'radio')
    radio.textContent = `Вариант ${i + 1}`
    radio.addEventListener('click', () => clicked.push(i))
    root.appendChild(radio)
  }
  document.body.appendChild(root)
  return { root, clicked }
}

function radios(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>('[role="radio"]')]
}

/** Нажатие клавиши в группе: возвращает, перехватила ли страница её. */
function press(root: HTMLElement, key: string): boolean {
  let prevented = false
  const event = {
    key,
    currentTarget: root,
    preventDefault: () => {
      prevented = true
    },
  } as unknown as ReactKeyboardEvent<HTMLElement>
  rovingKeyDown(event)
  return prevented
}

describe('клавиши группы радио', () => {
  it('стрелка вправо переносит выбор на следующий вариант', () => {
    const { root, clicked } = group()
    const items = radios(root)
    items[0].focus()
    press(root, 'ArrowRight')
    expect(document.activeElement).toBe(items[1])
    expect(clicked).toEqual([1])
  })

  it('стрелка вниз переносит выбор так же', () => {
    const { root, clicked } = group()
    const items = radios(root)
    items[0].focus()
    press(root, 'ArrowDown')
    expect(document.activeElement).toBe(items[1])
    expect(clicked).toEqual([1])
  })

  it('с первого варианта стрелка влево переходит на последний', () => {
    const { root, clicked } = group()
    const items = radios(root)
    items[0].focus()
    press(root, 'ArrowLeft')
    expect(document.activeElement).toBe(items[2])
    expect(clicked).toEqual([2])
  })

  it('Home переносит на первый вариант, End на последний', () => {
    const { root } = group()
    const items = radios(root)
    items[1].focus()
    press(root, 'Home')
    expect(document.activeElement).toBe(items[0])
    press(root, 'End')
    expect(document.activeElement).toBe(items[2])
  })

  it('обычная буква группу не трогает', () => {
    const { root, clicked } = group()
    const items = radios(root)
    items[0].focus()
    const prevented = press(root, 'a')
    expect(prevented).toBe(false)
    expect(document.activeElement).toBe(items[0])
    expect(clicked).toEqual([])
  })

  it('фокус вне группы ничего не меняет', () => {
    const { root, clicked } = group()
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    outside.focus()
    press(root, 'ArrowRight')
    expect(document.activeElement).toBe(outside)
    expect(clicked).toEqual([])
  })

  it('одиночный вариант остаётся на месте', () => {
    const { root, clicked } = group(1)
    const items = radios(root)
    items[0].focus()
    press(root, 'ArrowRight')
    expect(document.activeElement).toBe(items[0])
    expect(clicked).toEqual([0])
  })
})

describe('остановка Tab в группе радио', () => {
  it('выбранный вариант единственный, на котором Tab останавливается', () => {
    expect(rovingTabIndex(true, false, true)).toBe(0)
    expect(rovingTabIndex(false, true, true)).toBe(-1)
  })

  it('если ничего не выбрано, остановкой Tab будет первый вариант', () => {
    expect(rovingTabIndex(false, true, false)).toBe(0)
    expect(rovingTabIndex(false, false, false)).toBe(-1)
  })
})
