import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getCroppedImageFile } from '../../src/utils/cropImage'

/** Картинка, которую браузер уже загрузил. */
class FakeImage extends EventTarget {
  crossOrigin = ''
  private current = ''

  get src(): string {
    return this.current
  }

  set src(value: string) {
    this.current = value
    setTimeout(() => this.dispatchEvent(new Event('load')), 0)
  }
}

const drawImage = vi.fn()
let canvas: HTMLCanvasElement | null = null
let blob: Blob | null = new Blob(['картинка'], { type: 'image/webp' })
const realCreateElement = document.createElement
const originalGetContext = HTMLCanvasElement.prototype.getContext
const originalToBlob = HTMLCanvasElement.prototype.toBlob

beforeEach(() => {
  blob = new Blob(['картинка'], { type: 'image/webp' })
  canvas = null
  drawImage.mockClear()
  globalThis.Image = FakeImage as unknown as typeof Image
  // Холст создаётся внутри модуля, поэтому он запоминается тут
  document.createElement = ((tag: string, options?: ElementCreationOptions) => {
    const element = realCreateElement.call(document, tag, options)
    if (tag === 'canvas') canvas = element as HTMLCanvasElement
    return element
  }) as typeof document.createElement
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({ drawImage })) as unknown as HTMLCanvasElement['getContext']
  HTMLCanvasElement.prototype.toBlob = function (callback: BlobCallback) {
    callback(blob)
  }
})

afterEach(() => {
  document.createElement = realCreateElement
  HTMLCanvasElement.prototype.getContext = originalGetContext
  HTMLCanvasElement.prototype.toBlob = originalToBlob
})

/** Область капки, как её отдаёт редактор обрезки. */
const area = { x: 10, y: 20, width: 2000, height: 2000 }

describe('обрезанное фото', () => {
  it('сторона картинки не больше тысячи пикселей', async () => {
    await getCroppedImageFile('blob:фото', area, 'Рекс.jpg')
    expect(canvas?.width).toBe(1000)
    expect(canvas?.height).toBe(1000)
  })

  it('маленький кроп остаётся своего размера', async () => {
    await getCroppedImageFile('blob:фото', { x: 0, y: 0, width: 300, height: 300 }, 'Рекс.jpg')
    expect(canvas?.width).toBe(300)
  })

  it('в картинку попадает именно выбранная область', async () => {
    await getCroppedImageFile('blob:фото', { x: 10, y: 20, width: 300, height: 300 }, 'Рекс.jpg')
    expect(drawImage).toHaveBeenCalledTimes(1)
    const args = drawImage.mock.calls[0] as unknown[]
    expect(args.slice(1)).toEqual([10, 20, 300, 300, 0, 0, 300, 300])
  })

  it('файл получает расширение по типу картинки', async () => {
    const file = await getCroppedImageFile('blob:фото', area, 'Рекс.jpg')
    expect(file.name).toBe('Рекс.webp')
    expect(file.type).toBe('image/webp')
  })

  it('браузер без WebP отдаёт PNG', async () => {
    blob = new Blob(['картинка'], { type: 'image/png' })
    const file = await getCroppedImageFile('blob:фото', area, 'Рекс.jpg')
    expect(file.name).toBe('Рекс.png')
    expect(file.type).toBe('image/png')
  })

  it('имя без расширения не получает лишней точки', async () => {
    const file = await getCroppedImageFile('blob:фото', area, 'Рекс')
    expect(file.name).toBe('Рекс.webp')
  })

  it('если холст не получился, понятная ошибка вместо пустого файла', async () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as unknown as HTMLCanvasElement['getContext']
    await expect(getCroppedImageFile('blob:фото', area, 'Рекс.jpg')).rejects.toThrow('Canvas 2D context unavailable')
  })

  it('если картинка не получилась, понятная ошибка вместо пустого файла', async () => {
    HTMLCanvasElement.prototype.toBlob = function (callback: BlobCallback) {
      callback(null)
    }
    await expect(getCroppedImageFile('blob:фото', area, 'Рекс.jpg')).rejects.toThrow('Canvas is empty')
  })
})
