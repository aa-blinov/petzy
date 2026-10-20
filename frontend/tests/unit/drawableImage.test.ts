import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { drawableImage, isHeicFile } from '../../src/utils/drawableImage'

const api = vi.hoisted(() => ({ post: vi.fn() }))

vi.mock('../../src/services/api', () => ({ default: api }))

/** Файл телефона: у HEIC тип известен, у некоторых нет. */
function file(name: string, type: string): File {
  return new File(['данные'], name, { type })
}

beforeEach(() => {
  api.post.mockReset()
  api.post.mockResolvedValue({ data: new Blob(['картинка'], { type: 'image/webp' }) })
})

afterEach(() => {
  delete (globalThis as { createImageBitmap?: unknown }).createImageBitmap
})

describe('какой файл считается HEIC', () => {
  it('фото в формате HEIC', () => {
    expect(isHeicFile(file('photo.heic', 'image/heic'))).toBe(true)
  })

  it('фото в формате HEIF', () => {
    expect(isHeicFile(file('photo.heif', 'image/heif'))).toBe(true)
  })

  it('фото без типа, но с расширением HEIC', () => {
    expect(isHeicFile(file('photo.HEIC', ''))).toBe(true)
  })

  it('обычное фото не HEIC', () => {
    expect(isHeicFile(file('photo.jpg', 'image/jpeg'))).toBe(false)
  })
})

describe('фото для показа', () => {
  it('обычное фото отдаётся как есть, без обращения к серверу', async () => {
    const original = file('photo.jpg', 'image/jpeg')
    const result = await drawableImage(original)
    expect(result).toBe(original)
    expect(api.post).not.toHaveBeenCalled()
  })

  it('HEIC, который браузер рисует, отдаётся как есть', async () => {
    const close = vi.fn()
    globalThis.createImageBitmap = vi.fn(async () => ({ close })) as unknown as typeof createImageBitmap
    const original = file('photo.heic', 'image/heic')
    const result = await drawableImage(original)
    expect(result).toBe(original)
    expect(close).toHaveBeenCalled()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('HEIC, который браузер не рисует, уходит на сервер', async () => {
    globalThis.createImageBitmap = vi.fn(async () => {
      throw new Error('не умею')
    }) as unknown as typeof createImageBitmap
    const onWait = vi.fn()
    const original = file('photo.heic', 'image/heic')
    const result = await drawableImage(original, onWait)
    expect(result).toBeInstanceOf(Blob)
    expect(api.post).toHaveBeenCalledTimes(1)
    expect(api.post.mock.calls[0][0]).toBe('/images/preview')
    expect(onWait).toHaveBeenCalled()
  })

  it('HEIC без типа уходит на сервер как image/heic', async () => {
    globalThis.createImageBitmap = vi.fn(async () => {
      throw new Error('не умею')
    }) as unknown as typeof createImageBitmap
    await drawableImage(file('photo.heic', ''))
    const form = api.post.mock.calls[0][1] as FormData
    const sent = form.get('file') as File
    expect(sent.type).toBe('image/heic')
  })
})
