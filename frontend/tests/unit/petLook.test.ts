import { describe, expect, it, vi } from 'vitest'
import {
  FRAME_ASPECT,
  PET_ACCENTS,
  PET_BACKDROPS,
  PET_FONTS,
  PET_FRAMES,
  PET_SCENES,
  PET_VIBES,
  ROUND_FRAMES,
  frameWindowShape,
  loadPetFont,
  petAccentAttr,
  petAccentHex,
  petBackdropKey,
  petCropOf,
  petCropStyle,
  petFontOf,
  petFontStyle,
  petFrameAspect,
  petFrameOf,
  petFrameStyle,
  petLookOf,
  petSceneStyle,
  type PetFont,
  type PetLook,
} from '../../src/utils/petLook'

/** Свой шрифт вместо настоящего:грузка подменена, чтобы видеть, сколько раз её звали. */
function fakeFont(key: string, load: () => Promise<unknown>): PetFont {
  return { key, label: key, family: key, weight: 400, scale: 1, line: 1, load } as unknown as PetFont
}

describe('цвет питомца', () => {
  it('известный цвет ставится атрибутом на карточку', () => {
    expect(petAccentAttr({ accent: 'sage' })).toEqual({ 'data-pet-accent': 'sage' })
  })

  it('неизвестный цвет не ставится: красить нечем', () => {
    expect(petAccentAttr({ accent: 'chartreuse' })).toEqual({})
  })

  it('без цвета атрибута нет', () => {
    expect(petAccentAttr({})).toEqual({})
    expect(petAccentAttr(null)).toEqual({})
  })

  it('в палитре у каждого цвета свой ключ', () => {
    const keys = PET_ACCENTS.map((a) => a.key)
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('образ питомца', () => {
  it('у питомца без образа образ пустой', () => {
    expect(petLookOf({ look: undefined })).toEqual({})
    expect(petLookOf(null)).toEqual({})
  })

  it('образ питомца возвращается как есть', () => {
    const look: PetLook = { accent: 'sky' }
    expect(petLookOf({ look })).toBe(look)
  })
})

describe('рукописный шрифт имени', () => {
  it('известный шрифт находится', () => {
    expect(petFontOf({ font: 'caveat' })?.family).toBe('Caveat')
  })

  it('неизвестный шрифт не находится', () => {
    expect(petFontOf({ font: 'comic' })).toBeUndefined()
    expect(petFontOf({})).toBeUndefined()
  })

  it('шрифт грузится один раз, второй вызов отдаёт тот же запрос', async () => {
    const load = vi.fn(() => Promise.resolve())
    const font = fakeFont('test-once', load)
    const first = loadPetFont(font)
    const second = loadPetFont(font)
    await first
    expect(second).toBe(first)
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('после неудачной загрузки шрифт грузится заново', async () => {
    const load = vi.fn(() => Promise.reject(new Error('offline')))
    const font = fakeFont('test-retry', load)
    await loadPetFont(font)
    await loadPetFont(font)
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('без шрифта имя остаётся обычным', () => {
    expect(petFontStyle(undefined, '20px')).toEqual({})
  })

  it('рукописный шрифт задаёт гарнитуру, размер и интерлиньяж', () => {
    const style = petFontStyle(PET_FONTS[0], '20px')
    expect(style.fontFamily).toBe("'Caveat', var(--font-display)")
    expect(style.fontWeight).toBe(700)
    expect(style.fontSize).toBe('calc(20px * 1.55)')
    expect(style.lineHeight).toBe(1.22)
  })
})

describe('рамка фотографии', () => {
  it('известная рамка находится', () => {
    expect(petFrameOf({ frame: 'polaroid' })?.label).toBe('Полароид')
  })

  it('неизвестная рамка не находится', () => {
    expect(petFrameOf({ frame: 'ribbon' })).toBeUndefined()
    expect(petFrameOf({})).toBeUndefined()
  })

  it('у поляроида окно шире, чем выше', () => {
    expect(petFrameAspect('polaroid')).toBeCloseTo(102 / 91, 5)
    expect(petFrameAspect('polaroid')).toBeGreaterThan(1)
  })

  it('у плёнки окно выше, чем шире', () => {
    expect(petFrameAspect('film')).toBeCloseTo(92 / 112, 5)
    expect(petFrameAspect('film')).toBeLessThan(1)
  })

  it('у квадратной рамки окно остаётся квадратом', () => {
    expect(petFrameAspect('sticker')).toBe(1)
    expect(petFrameAspect(undefined)).toBe(1)
  })

  it('у рамок с особым соотношением сторон есть ключи в каталоге', () => {
    for (const key of Object.keys(FRAME_ASPECT)) {
      expect(PET_FRAMES.some((f) => f.key === key)).toBe(true)
    }
  })

  it('у круглых рамок есть ключи в каталоге', () => {
    for (const key of ROUND_FRAMES) {
      expect(PET_FRAMES.some((f) => f.key === key)).toBe(true)
    }
  })

  it('свой кадр берётся только для своей рамки', () => {
    const look: PetLook = { frame: 'heart', crops: { heart: { x: 10, y: 20, w: 50, h: 40 } } }
    expect(petCropOf(look)).toEqual({ x: 10, y: 20, w: 50, h: 40 })
  })

  it('без рамки кадра нет, даже если кадры сохранены', () => {
    expect(petCropOf({ crops: { heart: { x: 0, y: 0, w: 10, h: 10 } } })).toBeUndefined()
  })

  it('у рамки без своего кадра кадра нет', () => {
    expect(petCropOf({ frame: 'star', crops: { heart: { x: 0, y: 0, w: 10, h: 10 } } })).toBeUndefined()
  })

  it('кадр двигает и увеличивает фото по окну рамки', () => {
    const style = petCropStyle({ x: 10, y: 20, w: 50, h: 40 })
    expect(style.width).toBe('200%')
    expect(style.height).toBe('250%')
    expect(style.left).toBe('-20%')
    expect(style.top).toBe('-50%')
  })

  it('арка и сердце обводятся одним контуром', () => {
    expect(frameWindowShape('arch')?.outline).toBe(true)
    expect(frameWindowShape('heart')?.outline).toBe(true)
    expect(frameWindowShape('star')?.outline).toBe(true)
  })

  it('цветок, облако и лапа контуром не обводятся', () => {
    expect(frameWindowShape('flower')?.outline).toBe(false)
    expect(frameWindowShape('cloud')?.outline).toBe(false)
    expect(frameWindowShape('paw')?.outline).toBe(false)
  })

  it('у прямоугольной рамки своей формы нет', () => {
    expect(frameWindowShape('sticker')).toBeUndefined()
    expect(frameWindowShape('polaroid')).toBeUndefined()
  })

  it('неизвестная рамка не добавляет ничего', () => {
    expect(petFrameStyle('ribbon')).toEqual({ box: {} })
    expect(petFrameStyle(undefined)).toEqual({ box: {} })
  })

  it('у рамки-сториса круглая окантовка и круглое фото', () => {
    const style = petFrameStyle('story')
    expect(style.box.border).toBe('3px solid transparent')
    expect(style.image?.borderRadius).toBe('50%')
  })

  it('маленький образец рамки рисуется тоньше', () => {
    expect(petFrameStyle('story', 0.5).box.border).toBe('2px solid transparent')
  })

  it('неон берёт цвет питомца', () => {
    expect(petFrameStyle('neon').box.boxShadow).toContain('var(--app-accent-deep)')
  })
})

describe('подложка карточки', () => {
  it('выбранная подложка та, что выбрана', () => {
    expect(petBackdropKey({ backdrop: 'dots' })).toBe('dots')
  })

  it('выбранная «без подложки» не заменяется заливкой цвета', () => {
    expect(petBackdropKey({ backdrop: 'plain', accent: 'sage' })).toBe('plain')
  })

  it('неизвестная подложка откатывается на заливку цвета', () => {
    expect(petBackdropKey({ backdrop: 'ribbon', accent: 'sage' })).toBe('fill')
  })

  it('без подложки цвет питомца даёт заливку', () => {
    expect(petBackdropKey({ accent: 'sage' })).toBe('fill')
  })

  it('без подложки и без цвета подложки нет', () => {
    expect(petBackdropKey({})).toBe('plain')
    expect(petBackdropKey(null)).toBe('plain')
  })

  it('цвет подложки берётся из палитры', () => {
    expect(petAccentHex({ accent: 'sage' })).toBe('#5E9A56')
  })

  it('неизвестный цвет даёт цвет бренда', () => {
    expect(petAccentHex({ accent: 'chartreuse' })).toBe('#C46A3F')
    expect(petAccentHex({})).toBe('#C46A3F')
  })
})

describe('фон ленты', () => {
  it('выбранная сцена красит фон ленты', () => {
    const style = petSceneStyle({ scene: 'dots', accent: 'sage' })
    expect(style.background).toContain('radial-gradient')
    expect(style.background).toContain('var(--pet-soft')
  })

  it('сцена «без подложки» фон не красит', () => {
    expect(petSceneStyle({ scene: 'plain' })).toEqual({})
    expect(petSceneStyle({})).toEqual({})
  })

  it('фотография не ставится фоном ленты', () => {
    expect(petSceneStyle({ scene: 'photo' })).toEqual({})
  })

  it('фотографии нет среди сцен для ленты', () => {
    expect(PET_SCENES.some((s) => s.key === 'photo')).toBe(false)
    expect(PET_SCENES.length).toBe(PET_BACKDROPS.length - 1)
  })
})

describe('готовые образы', () => {
  it('ссылаются на ключи, которые есть в каталогах', () => {
    for (const vibe of PET_VIBES) {
      expect(PET_ACCENTS.some((a) => a.key === vibe.look.accent)).toBe(true)
      if (vibe.look.font) expect(PET_FONTS.some((f) => f.key === vibe.look.font)).toBe(true)
      expect(PET_FRAMES.some((f) => f.key === vibe.look.frame)).toBe(true)
      expect(PET_BACKDROPS.some((b) => b.key === vibe.look.backdrop)).toBe(true)
    }
  })

  it('не трогают подпись под именем', () => {
    for (const vibe of PET_VIBES) {
      expect(vibe.look).not.toHaveProperty('tagline')
    }
  })
})
