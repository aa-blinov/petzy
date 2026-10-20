import { beforeEach, describe, expect, it } from 'vitest'
import { announce } from '../../src/utils/announce'

/** Один кадр: сообщение попадает в область на следующем кадре. */
function frame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()))
}

function liveRegion(politeness: 'polite' | 'assertive'): HTMLElement {
  const el = document.querySelector<HTMLElement>(`[aria-live="${politeness}"]`)
  if (!el) throw new Error(`области ${politeness} нет на странице`)
  return el
}

beforeEach(() => {
  for (const el of document.querySelectorAll<HTMLElement>('[aria-live]')) el.textContent = ''
})

describe('объявления для экранного диктора', () => {
  it('обе области живут на странице с самого начала', () => {
    expect(liveRegion('polite')).toBeTruthy()
    expect(liveRegion('assertive')).toBeTruthy()
  })

  it('подтверждение читается в области polite', async () => {
    announce('Запись сохранена')
    await frame()
    expect(liveRegion('polite').textContent).toBe('Запись сохранена')
  })

  it('ошибка читается в области assertive, а polite остаётся пустой', async () => {
    announce('Не получилось сохранить', 'assertive')
    await frame()
    expect(liveRegion('assertive').textContent).toBe('Не получилось сохранить')
    expect(liveRegion('polite').textContent).toBe('')
  })

  it('область ошибки помечена как alert, а подтверждения как status', () => {
    expect(liveRegion('assertive').getAttribute('role')).toBe('alert')
    expect(liveRegion('polite').getAttribute('role')).toBe('status')
  })

  it('одно и то же сообщение дважды подряд читается снова', async () => {
    const polite = liveRegion('polite')
    announce('Сохранено')
    await frame()

    // Область должна опустеть перед новым текстом: иначе второй раз читать нечего
    const cleared: string[] = []
    const observer = new MutationObserver((list) => {
      for (const record of list) {
        if (record.removedNodes.length > 0 && record.addedNodes.length === 0) {
          cleared.push(record.removedNodes[0].textContent ?? '')
        }
      }
    })
    observer.observe(polite, { childList: true })

    announce('Сохранено')
    await frame()
    await Promise.resolve()
    observer.disconnect()

    expect(cleared).toContain('Сохранено')
  })

  it('сообщение не появляется в области раньше следующего кадра', () => {
    announce('Сохранено')
    expect(liveRegion('polite').textContent).toBe('')
  })
})
