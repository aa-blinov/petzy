/**
 * How a pet's card shows it: a short line about the pet and a colour from a fixed palette.
 *
 * The name on the card can also take a hand-written face (PET_FONTS), served from the app like the others and loaded
 * only when a pet uses it or the settings page shows them: about 45 KB each, never part of the install.
 *
 * The colours are only names here; the tints are in globals.css (`[data-pet-accent]`), light and dark, each checked at
 * 5:1 or better for its deep tone on its soft one. The server knows the same names (PET_ACCENTS in web/schemas.py).
 */

import type { CSSProperties } from 'react';
import type { Pet } from '../services/pets.service';

export const PET_TAGLINE_MAX = 40;

export interface PetCrop {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PetLook {
  tagline?: string;
  accent?: string;
  /** A key of PET_FONTS: the hand-written face of the name on the card. */
  font?: string;
  /** A key of PET_FRAMES: the frame around the photo (or the species picture) on the card. */
  frame?: string;
  /** A key of PET_BACKDROPS: what lies behind the card. Empty: a fill when there is a colour, nothing without. */
  backdrop?: string;
  /** The same catalogue behind the whole feed area of the pet; empty: none. */
  scene?: string;
  /** A palette colour for the backdrop alone, when it is not the card's own. */
  tint?: string;
  /** The part of the photo each frame shows: every frame has a window of its own shape, so its own part. */
  crops?: Record<string, PetCrop>;
}

/** `swatch` is the deep tone in the light theme, for the picker button only; the card takes its tints from the CSS. */
export const PET_ACCENTS = [
  { key: 'sage', label: 'Шалфей', swatch: '#5E9A56' },
  { key: 'sky', label: 'Небо', swatch: '#4A8CC7' },
  { key: 'lilac', label: 'Сирень', swatch: '#8466C4' },
  { key: 'rose', label: 'Роза', swatch: '#D4577C' },
  { key: 'sun', label: 'Солнце', swatch: '#D1990F' },
  { key: 'teal', label: 'Бирюза', swatch: '#3A9C95' },
  { key: 'slate', label: 'Графит', swatch: '#6B7A90' },
] as const;

/** The attribute that re-tints a subtree: absent for the brand copper (no colour chosen, or one the palette lost). */
export function petAccentAttr(look?: PetLook | null): { 'data-pet-accent'?: string } {
  const accent = look?.accent;
  return accent && PET_ACCENTS.some((a) => a.key === accent) ? { 'data-pet-accent': accent } : {};
}

export function petLookOf(pet?: Pick<Pet, 'look'> | null): PetLook {
  return pet?.look ?? {};
}

/**
 * Hand-written faces with Cyrillic and Latin (a name may be either). `scale` evens out their very different sizes at the
 * same font-size: Amatic is tiny, Pacifico wide. Their files are loaded on demand, see loadPetFont.
 */
export const PET_FONTS = [
  { key: 'caveat', label: 'Живой почерк', family: 'Caveat', weight: 700, scale: 1.55, load: () => Promise.all([import('@fontsource/caveat/cyrillic-700.css'), import('@fontsource/caveat/latin-700.css')]) },
  { key: 'marck', label: 'Перо', family: 'Marck Script', weight: 400, scale: 1.4, load: () => Promise.all([import('@fontsource/marck-script/cyrillic-400.css'), import('@fontsource/marck-script/latin-400.css')]) },
  { key: 'bad', label: 'Письмо', family: 'Bad Script', weight: 400, scale: 1.4, load: () => Promise.all([import('@fontsource/bad-script/cyrillic-400.css'), import('@fontsource/bad-script/latin-400.css')]) },
  { key: 'pacifico', label: 'Мягкая кисть', family: 'Pacifico', weight: 400, scale: 1.05, load: () => Promise.all([import('@fontsource/pacifico/cyrillic-400.css'), import('@fontsource/pacifico/latin-400.css')]) },
  { key: 'neucha', label: 'Мелки', family: 'Neucha', weight: 400, scale: 1.3, load: () => Promise.all([import('@fontsource/neucha/cyrillic-400.css'), import('@fontsource/neucha/latin-400.css')]) },
  { key: 'amatic', label: 'Тонкий', family: 'Amatic SC', weight: 700, scale: 1.75, load: () => Promise.all([import('@fontsource/amatic-sc/cyrillic-700.css'), import('@fontsource/amatic-sc/latin-700.css')]) },
] as const;

export type PetFont = (typeof PET_FONTS)[number];

export function petFontOf(look?: PetLook | null): PetFont | undefined {
  return PET_FONTS.find((f) => f.key === look?.font);
}

const loading = new Map<string, Promise<unknown>>();

/** Fetches a face once; the name shows in the fallback face until it lands (font-display: swap). */
export function loadPetFont(font: PetFont): Promise<unknown> {
  let pending = loading.get(font.key);
  if (!pending) {
    pending = font.load().catch(() => {
      // Offline and never cached: the name stays in the ordinary face. Try again next time.
      loading.delete(font.key);
    });
    loading.set(font.key, pending);
  }
  return pending;
}

/** The inline style that sets a name in the face, or none for the ordinary one. */
export function petFontStyle(font: PetFont | undefined, baseSize: string): { fontFamily?: string; fontWeight?: number; fontSize?: string; letterSpacing?: string } {
  if (!font) return {};
  return { fontFamily: `'${font.family}', var(--font-display)`, fontWeight: font.weight, fontSize: `calc(${baseSize} * ${font.scale})`, letterSpacing: '0' };
}

export const PET_FRAME_GROUPS = [
  { key: 'style', label: 'Стиль' },
  { key: 'material', label: 'Материалы' },
  { key: 'shape', label: 'Формы' },
] as const;

export const PET_FRAMES = [
  { key: 'story', label: 'Сторис', group: 'style' },
  { key: 'sticker', label: 'Стикер', group: 'style' },
  { key: 'neon', label: 'Неон', group: 'style' },
  { key: 'holo', label: 'Голограмма', group: 'style' },
  { key: 'popart', label: 'Поп-арт', group: 'style' },
  { key: 'glitch', label: 'Глитч', group: 'style' },
  { key: 'aura', label: 'Аура', group: 'style' },
  { key: 'polaroid', label: 'Полароид', group: 'style' },
  { key: 'film', label: 'Плёнка', group: 'style' },
  { key: 'stamp', label: 'Марка', group: 'style' },
  { key: 'gold', label: 'Золото', group: 'material' },
  { key: 'gallery', label: 'Дерево', group: 'material' },
  { key: 'marble', label: 'Мрамор', group: 'material' },
  { key: 'porthole', label: 'Металл', group: 'material' },
  { key: 'leather', label: 'Кожа', group: 'material' },
  { key: 'denim', label: 'Джинса', group: 'material' },
  { key: 'kraft', label: 'Крафт', group: 'material' },
  { key: 'velvet', label: 'Бархат', group: 'material' },
  { key: 'glitter', label: 'Блёстки', group: 'material' },
  { key: 'pearl', label: 'Перламутр', group: 'material' },
  { key: 'glass', label: 'Стекло', group: 'material' },
  { key: 'carbon', label: 'Карбон', group: 'material' },
  { key: 'rope', label: 'Канат', group: 'material' },
  { key: 'arch', label: 'Арка', group: 'shape' },
  { key: 'circle', label: 'Круг', group: 'shape' },
  { key: 'flower', label: 'Цветок', group: 'shape' },
  { key: 'heart', label: 'Сердце', group: 'shape' },
  { key: 'star', label: 'Звезда', group: 'shape' },
  { key: 'cloud', label: 'Облако', group: 'shape' },
  { key: 'paw', label: 'Лапка', group: 'shape' },
] as const;

export function petFrameOf(look?: PetLook | null): (typeof PET_FRAMES)[number] | undefined {
  return PET_FRAMES.find((f) => f.key === look?.frame);
}

/** The frames whose window is round: the crop editor shows a round window for them. */
export const ROUND_FRAMES = ['story', 'porthole', 'circle'];

/**
 * Width over height of the window each frame leaves for the photo (at the card's 112 px), so the crop editor cuts the
 * shape the card will show: the polaroid's is wider than tall, the film strip's taller. Not listed: square.
 */
export const FRAME_ASPECT: Record<string, number> = { polaroid: 102 / 91, film: 92 / 112 };

export function petFrameAspect(frame: string | undefined): number {
  return (frame && FRAME_ASPECT[frame]) || 1;
}

/** The saved part of the photo for the frame the pet wears, if one was chosen. */
export function petCropOf(look?: PetLook | null): PetCrop | undefined {
  return look?.frame ? look.crops?.[look.frame] : undefined;
}

/** A shape cut out of the picture by a mask drawn in a 100 x 100 box; the photo takes its outline. */
function shapeMask(inner: string): CSSProperties {
  const url = `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>${inner}</svg>`)}")`;
  return {
    borderRadius: 0,
    background: 'transparent',
    WebkitMaskImage: url,
    maskImage: url,
    WebkitMaskSize: '100% 100%',
    maskSize: '100% 100%',
    WebkitMaskRepeat: 'no-repeat',
    maskRepeat: 'no-repeat',
  };
}

const ring = (n: number, r: number, f: (x: number, y: number, i: number) => string) =>
  Array.from({ length: n }, (_, i) => {
    const a = (i * 2 * Math.PI) / n - Math.PI / 2;
    return f(+(50 + r * Math.cos(a)).toFixed(1), +(50 + r * Math.sin(a)).toFixed(1), i);
  }).join('');

const SHAPES: Record<string, string> = {
  // Eight petals round a centre.
  flower: `<g fill='#000'><circle cx='50' cy='50' r='33'/>${ring(8, 31, (x, y) => `<circle cx='${x}' cy='${y}' r='19'/>`)}</g>`,
  heart: `<path fill='#000' d='M50 90 C18 67 5 49 5 32 C5 17 17 8 30 8 C39 8 46 13 50 21 C54 13 61 8 70 8 C83 8 95 17 95 32 C95 49 82 67 50 90 Z'/>`,
  // A seal: the points of a badge.
  star: `<path fill='#000' d='${Array.from({ length: 32 }, (_, i) => {
    const a = (i * Math.PI) / 16 - Math.PI / 2;
    const r = i % 2 === 0 ? 49 : 41;
    return `${i === 0 ? 'M' : 'L'}${(50 + r * Math.cos(a)).toFixed(1)} ${(50 + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ')} Z'/>`,
  cloud: `<g fill='#000'><circle cx='27' cy='63' r='19'/><circle cx='47' cy='42' r='25'/><circle cx='72' cy='50' r='21'/><circle cx='50' cy='67' r='24'/><circle cx='77' cy='69' r='17'/></g>`,
  // A big pad and four toes.
  paw: `<g fill='#000'><ellipse cx='50' cy='69' rx='28' ry='23'/><ellipse cx='19' cy='44' rx='11' ry='15' transform='rotate(-22 19 44)'/><ellipse cx='39' cy='23' rx='11' ry='15' transform='rotate(-7 39 23)'/><ellipse cx='61' cy='23' rx='11' ry='15' transform='rotate(7 61 23)'/><ellipse cx='81' cy='44' rx='11' ry='15' transform='rotate(22 81 44)'/></g>`,
  // A postage stamp: paper with a perforated edge.
  stamp: `<mask id='m'><rect width='100' height='100' fill='#fff'/><g fill='#000'>${Array.from({ length: 10 }, (_, i) => {
    const c = 5 + i * 10;
    return `<circle cx='${c}' cy='0' r='3.2'/><circle cx='${c}' cy='100' r='3.2'/><circle cx='0' cy='${c}' r='3.2'/><circle cx='100' cy='${c}' r='3.2'/>`;
  }).join('')}</g></mask><rect width='100' height='100' fill='#000' mask='url(#m)'/>`,
};

/**
 * A grain drawn by the browser (SVG turbulence), laid over a colour as one more background layer, so a rim reads as wood,
 * paper or leather and not as a flat fill. `alpha` is how dark or bright the grain is, `freq` how fine.
 */
function grain(freq: number, alpha: number, light = false): string {
  const c = light ? '1 1 1' : '0 0 0';
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='${freq}' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 ${c.split(' ')[0]} 0 0 0 0 ${c.split(' ')[1]} 0 0 0 0 ${c.split(' ')[2]} 0 0 0 ${alpha * 2} ${-alpha / 2}'/></filter><rect width='160' height='160' filter='url(#n)'/></svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

/** A frame that is a rim of one material round the photo: the material on the border, an inner mat behind the photo. */
function rim(width: number, paint: string, extra: CSSProperties = {}, mat = 'transparent'): CSSProperties {
  return {
    boxSizing: 'border-box',
    border: `${width}px solid transparent`,
    background: `linear-gradient(${mat}, ${mat}) padding-box, ${paint} border-box`,
    boxShadow: '0 3px 8px rgba(0, 0, 0, 0.35)',
    ...extra,
  };
}

/**
 * The window a frame leaves, as a shape in a 100 x 100 box, for the crop editor to show: the same outline the frame cuts. Only
 * the frames that are a shape have one; the rest are a rectangle or a circle, which the editor draws itself. `outline` says
 * whether the edge can be stroked (a single path, not several circles overlapped).
 */
export function frameWindowShape(frame: string): { inner: string; outline: boolean } | undefined {
  if (frame === 'arch') return { inner: `<path fill='#000' d='M0 100 L0 52 C0 20 22 0 50 0 C78 0 100 20 100 52 L100 100 Z'/>`, outline: true };
  if (frame === 'heart' || frame === 'star') return { inner: SHAPES[frame], outline: true };
  if (frame === 'flower' || frame === 'cloud' || frame === 'paw') return { inner: SHAPES[frame], outline: false };
  return undefined;
}

export interface PetFrameStyle {
  /** On the box that holds the picture; it keeps its size: shadows and rotation draw outside it, borders sit inside it. */
  box: CSSProperties;
  /** On the photo inside, where the box's own rounding is not enough. */
  image?: CSSProperties;
}

/**
 * What a frame adds to the picture, drawn in CSS only. `scale` shrinks the widths for the small samples in the picker.
 * The neon and the pop-art shadow take the pet's colour, so they follow the accent chosen next to them; the rest have
 * colours of their own.
 */
export function petFrameStyle(frame: string | undefined, scale = 1): PetFrameStyle {
  const px = (n: number) => `${Math.max(1, Math.round(n * scale))}px`;
  switch (frame) {
    case 'story':
      // The round ring of a story: a gradient border, a gap, the photo round inside it.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(3)} solid transparent`,
          padding: px(3),
          borderRadius: '50%',
          background:
            'linear-gradient(var(--app-card-background), var(--app-card-background)) padding-box, linear-gradient(45deg, #feda75, #fa7e1e, #d62976, #962fbf, #4f5bd5) border-box',
        },
        image: { borderRadius: '50%' },
      };
    case 'sticker':
      // A die-cut sticker: a thick white edge, a soft shadow, a slight tilt.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(4)} solid #fff`,
          borderRadius: '28%',
          background: '#fff',
          boxShadow: '0 2px 0 rgba(0, 0, 0, 0.08), 0 6px 14px rgba(0, 0, 0, 0.25)',
          transform: 'rotate(3deg)',
        },
      };
    case 'neon':
      return {
        box: {
          boxShadow: `0 0 0 ${px(2)} var(--app-accent-deep), 0 0 ${px(12)} var(--app-accent-deep), 0 0 ${px(22)} color-mix(in srgb, var(--app-accent-deep) 45%, transparent)`,
        },
      };
    case 'holo':
      // The sheen of holographic foil: pastel stops that run round the edge.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(4)} solid transparent`,
          background:
            'linear-gradient(var(--app-accent-soft), var(--app-accent-soft)) padding-box, linear-gradient(135deg, #ff9ad5, #9ad1ff, #b8ffcf, #fff3a8, #d6a8ff, #ff9ad5) border-box',
        },
      };
    case 'polaroid':
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(5)} solid #fff`,
          borderBottomWidth: px(16),
          borderRadius: px(4),
          // Photo paper: a faint tooth in the white.
          background: `${grain(0.9, 0.07)}, #fbfaf6`,
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.28)',
          transform: 'rotate(-3deg)',
        },
      };
    case 'gallery': {
      // Oak with a visible grain and a cream mat, as hung in a gallery.
      const w = Math.max(2, Math.round(7 * scale));
      return {
        box: rim(
          w,
          `repeating-linear-gradient(90deg, rgba(50, 25, 8, 0.22) 0 1px, transparent 1px ${px(5)}), repeating-linear-gradient(86deg, rgba(255, 220, 160, 0.14) 0 ${px(2)}, transparent ${px(2)} ${px(11)}), ${grain(0.35, 0.2)}, linear-gradient(135deg, #8a5a2b, #b98650 38%, #744721 70%, #a36d3a)`,
          { padding: px(4), borderRadius: px(2) },
          '#f1ebdf',
        ),
      };
    }
    case 'porthole': {
      // Brushed steel: fine lines along the ring, a bright sweep across it, a dark glass behind the photo.
      const w = Math.max(2, Math.round(7 * scale));
      return {
        box: rim(
          w,
          `repeating-conic-gradient(from 0deg, rgba(255, 255, 255, 0.28) 0 0.6deg, rgba(0, 0, 0, 0.12) 0.6deg 1.2deg), conic-gradient(from 30deg, #f7f9fb, #8e9bab, #eef2f6, #5f6c7b, #f3f6f9)`,
          { borderRadius: '50%' },
          '#0b2a3c',
        ),
      };
    }
    case 'gold': {
      // Gold leaf: a long bright sweep, a brushed grain, a fine sparkle.
      const w = Math.max(2, Math.round(7 * scale));
      return {
        box: rim(
          w,
          `${grain(1.1, 0.12, true)}, repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.16) 0 1px, rgba(90, 55, 0, 0.1) 1px 2px), linear-gradient(135deg, #6f4a0a, #f6df8b 16%, #c48b1c 32%, #fff2b6 48%, #b27a14 64%, #f1d070 82%, #7d5410)`,
          { padding: px(2), borderRadius: px(3) },
          '#7d5410',
        ),
      };
    }
    case 'marble': {
      // White marble, grey veins running across it.
      const w = Math.max(2, Math.round(7 * scale));
      return {
        box: rim(
          w,
          `linear-gradient(118deg, transparent 38%, rgba(90, 96, 120, 0.62) 39%, transparent 42.5%), linear-gradient(62deg, transparent 54%, rgba(90, 96, 120, 0.46) 55%, transparent 58%), linear-gradient(160deg, transparent 20%, rgba(90, 96, 120, 0.34) 21%, transparent 22.5%), ${grain(0.6, 0.06)}, radial-gradient(circle at 28% 18%, #ffffff, #ececf2 55%, #d6d7e0)`,
          { borderRadius: px(3) },
          '#fff',
        ),
      };
    }
    case 'leather': {
      // Stitched leather: a pebbled brown rim with a row of thread along it.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `${grain(0.55, 0.32)}, ${grain(1.4, 0.16, true)}, linear-gradient(145deg, #8a4a24, #5e2f14 55%, #7a3f1c)`,
          { borderRadius: px(8), outline: `${Math.max(1, Math.round(1.5 * scale))}px dashed #f2d49a`, outlineOffset: `${-Math.round(w * 0.62)}px` },
          '#3b1d0c',
        ),
      };
    }
    case 'denim': {
      // Denim: a woven blue, contrast stitching in orange.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.09) 0 1px, transparent 1px 3px), repeating-linear-gradient(-45deg, rgba(0, 0, 0, 0.14) 0 1px, transparent 1px 3px), ${grain(0.8, 0.12)}, linear-gradient(135deg, #3b6a9c, #2b5483 60%, #36628f)`,
          { borderRadius: px(8), outline: `${Math.max(1, Math.round(1.5 * scale))}px dashed #f0a24a`, outlineOffset: `${-Math.round(w * 0.62)}px` },
          '#1d3a5c',
        ),
      };
    }
    case 'kraft': {
      // Kraft paper, packed with a cut line.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `${grain(0.7, 0.2)}, ${grain(0.12, 0.1)}, linear-gradient(120deg, #c9a46c, #d6b47e 50%, #bd965c)`,
          { borderRadius: px(3), outline: `${Math.max(1, Math.round(1.5 * scale))}px dashed rgba(255, 255, 255, 0.85)`, outlineOffset: `${-Math.round(w * 0.6)}px`, transform: 'rotate(-1.5deg)' },
          '#e7d6b8',
        ),
      };
    }
    case 'velvet': {
      // Velvet: deep colour, a soft sheen where the light falls, a nap that takes it away at the edges.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `${grain(1.2, 0.14, true)}, radial-gradient(circle at 25% 20%, #c32a73, transparent 55%), radial-gradient(circle at 80% 90%, #2b0716, transparent 60%), linear-gradient(135deg, #7a1244, #4b0b2b)`,
          { borderRadius: px(10) },
          '#2b0716',
        ),
      };
    }
    case 'glitter': {
      // Glitter: sparks of every colour on a pink and violet ground.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `${grain(1.6, 0.9, true)}, ${grain(0.9, 0.3, true)}, linear-gradient(135deg, #ff6fb5, #b45cff 50%, #5c8bff)`,
          { borderRadius: px(10) },
          '#3a0f55',
        ),
      };
    }
    case 'pearl': {
      // Mother-of-pearl: pale colours that turn with the angle.
      const w = Math.max(3, Math.round(8 * scale));
      return {
        box: rim(
          w,
          `${grain(0.5, 0.05)}, conic-gradient(from 20deg, #fffaf5, #e5d6ff, #d4efff, #ffe6f1, #fff4d6, #fffaf5)`,
          { borderRadius: px(12) },
          '#fff',
        ),
      };
    }
    case 'glass':
      // Frosted glass: a pale, see-through rim with a bright edge, lit from above.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(9)} solid rgba(255, 255, 255, 0.34)`,
          borderRadius: px(18),
          backdropFilter: 'blur(8px)',
          WebkitBackdropFilter: 'blur(8px)',
          boxShadow: `0 0 0 ${px(1)} rgba(255, 255, 255, 0.7), inset 0 ${px(2)} ${px(3)} rgba(255, 255, 255, 0.6), 0 ${px(6)} ${px(16)} rgba(0, 0, 0, 0.22)`,
        },
      };
    case 'carbon': {
      // Carbon fibre: the black twill of a race car.
      const t = Math.max(4, Math.round(10 * scale));
      const w = Math.max(3, Math.round(8 * scale));
      return {
        box: rim(
          w,
          `linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent 40%), linear-gradient(45deg, #1b1b1b 25%, transparent 25% 75%, #1b1b1b 75%) 0 0 / ${t * 2}px ${t * 2}px, linear-gradient(45deg, #1b1b1b 25%, #2c2c2c 25% 75%, #1b1b1b 75%) ${t}px ${t}px / ${t * 2}px ${t * 2}px, #232323`,
          { borderRadius: px(4) },
          '#0c0c0c',
        ),
      };
    }
    case 'rope': {
      // A twisted rope: bands that run round the photo at a slant.
      const w = Math.max(3, Math.round(9 * scale));
      return {
        box: rim(
          w,
          `repeating-linear-gradient(45deg, #e2c58a 0 ${px(3)}, #9c7a3f ${px(3)} ${px(4.5)}, #c8a665 ${px(4.5)} ${px(7.5)}, #7e6030 ${px(7.5)} ${px(9)})`,
          { borderRadius: px(12) },
          '#1d3a5c',
        ),
      };
    }
    case 'film':
      // A strip of film: a dark band with a column of light holes down each side.
      return {
        box: {
          boxSizing: 'border-box',
          padding: `0 ${px(10)}`,
          borderRadius: px(4),
          background: `repeating-linear-gradient(180deg, #111 0 ${px(3)}, #eee ${px(3)} ${px(7)}, #111 ${px(7)} ${px(10)}) left ${px(2.5)} top 0 / ${px(5)} 100% no-repeat, repeating-linear-gradient(180deg, #111 0 ${px(3)}, #eee ${px(3)} ${px(7)}, #111 ${px(7)} ${px(10)}) right ${px(2.5)} top 0 / ${px(5)} 100% no-repeat, #111`,
        },
      };
    case 'stamp':
      return { box: { ...shapeMask(SHAPES.stamp), boxSizing: 'border-box', padding: px(8), background: '#fff' } };
    case 'popart':
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(3)} solid var(--app-text-primary)`,
          borderRadius: px(6),
          boxShadow: `${px(6)} ${px(6)} 0 var(--app-accent-deep)`,
        },
      };
    case 'glitch':
      // Two colour channels slipped apart.
      return { box: { borderRadius: px(4), boxShadow: `${px(5)} ${px(4)} 0 #ff2d95, ${px(-5)} ${px(-4)} 0 #00e5ff` } };
    case 'aura':
      return {
        box: {
          boxShadow: `0 0 ${px(14)} ${px(2)} #ff7ab6, ${px(-9)} ${px(6)} ${px(20)} #7aa2ff, ${px(9)} ${px(-6)} ${px(20)} #ffd36e`,
        },
      };
    case 'arch':
      return { box: { borderRadius: `50% 50% ${px(10)} ${px(10)} / 42% 42% ${px(10)} ${px(10)}` } };
    case 'circle':
      return { box: { borderRadius: '50%' } };
    case 'flower':
    case 'heart':
    case 'star':
    case 'cloud':
    case 'paw':
      return { box: shapeMask(SHAPES[frame]) };
    default:
      return { box: {} };
  }
}

/** The photo's own box for a crop: the part of it in the window, set by where it starts and how much of it shows. */
export function petCropStyle(crop: PetCrop): CSSProperties {
  return {
    position: 'absolute',
    maxWidth: 'none',
    width: `${10000 / crop.w}%`,
    height: `${10000 / crop.h}%`,
    left: `${(-crop.x * 100) / crop.w}%`,
    top: `${(-crop.y * 100) / crop.h}%`,
    objectFit: 'cover',
  };
}

export const PET_BACKDROPS = [
  { key: 'plain', label: 'Без подложки' },
  { key: 'fill', label: 'Заливка' },
  { key: 'gradient', label: 'Градиент' },
  { key: 'aurora', label: 'Аврора' },
  { key: 'photo', label: 'Фото' },
  { key: 'dots', label: 'Горошек' },
  { key: 'stripes', label: 'Полоски' },
  { key: 'grid', label: 'Клетка' },
  { key: 'waves', label: 'Волны' },
  { key: 'paws', label: 'Лапки' },
  { key: 'stars', label: 'Звёзды' },
  { key: 'hearts', label: 'Сердечки' },
  { key: 'paper', label: 'Бумага' },
  { key: 'linen', label: 'Лён' },
] as const;

const COPPER = '#C46A3F';

/** What the card shows behind it: the chosen one, else a fill if the pet has a colour, else nothing. */
export function petBackdropKey(look?: PetLook | null): string {
  if (look?.backdrop && PET_BACKDROPS.some((b) => b.key === look.backdrop)) return look.backdrop;
  return look?.accent ? 'fill' : 'plain';
}

/** The tint attribute: a backdrop colour of its own, set on the card, read by the backdrop alone (see globals.css). */
export function petTintAttr(look?: PetLook | null): { 'data-pet-tint'?: string } {
  return look?.tint && PET_ACCENTS.some((a) => a.key === look.tint) ? { 'data-pet-tint': look.tint } : {};
}

/** The colour the backdrop's patterns are drawn in: the tint, else the pet's colour, else the brand's. */
export function petTintHex(look?: PetLook | null): string {
  const key = look?.tint || look?.accent;
  return PET_ACCENTS.find((a) => a.key === key)?.swatch ?? COPPER;
}

const soft = 'var(--bd-soft, var(--app-accent-soft))';
const deep = 'var(--bd-deep, var(--app-accent-deep))';
const base = 'var(--app-card-background)';
const wash = `color-mix(in srgb, ${soft} 38%, ${base})`;

/** A tile of small shapes in the colour, as a background layer; two rows offset, so it does not read as a grid. */
function tile(hex: string, alpha: number, shape: string, size = 56): string {
  const half = size / 2;
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${size}' height='${size}'><g fill='${hex}' fill-opacity='${alpha}'><g transform='translate(${half / 2} ${half / 2}) rotate(-14)'>${shape}</g><g transform='translate(${half + half / 2} ${half + half / 2}) rotate(12)'>${shape}</g></g></svg>`;
  return `url("data:image/svg+xml,${encodeURIComponent(svg)}") 0 0 / ${size}px ${size}px`;
}

const PAW = `<ellipse cx='0' cy='4' rx='5.5' ry='4.5'/><ellipse cx='-6' cy='-3' rx='2.2' ry='3'/><ellipse cx='-2' cy='-7' rx='2.2' ry='3'/><ellipse cx='2.5' cy='-7' rx='2.2' ry='3'/><ellipse cx='6.5' cy='-3' rx='2.2' ry='3'/>`;
const STAR = `<polygon points='0,-7 2,-2.2 7,-2 3,1.4 4.4,6.5 0,3.6 -4.4,6.5 -3,1.4 -7,-2 -2,-2.2'/>`;
const HEART = `<path d='M0 6 C-8 0 -7 -6 -3.4 -6 C-1.6 -6 -0.4 -5 0 -3.6 C0.4 -5 1.6 -6 3.4 -6 C7 -6 8 0 0 6 Z'/>`;

/**
 * The card's own background for a backdrop. Everything is a background layer or a variable, so it follows the theme; the
 * patterns are drawn in the colour passed (`hex`), faint enough to leave the text legible. `photo` is not here: it is a
 * blurred picture and needs an element of its own (see PetSummaryCard).
 */
export function petBackdropStyle(key: string, hex: string): CSSProperties {
  const faint = (a: number) => `${hex}${Math.round(a * 255).toString(16).padStart(2, '0')}`;
  switch (key) {
    case 'fill':
      return { background: `color-mix(in srgb, ${soft} 60%, ${base})` };
    case 'gradient':
      return { background: `linear-gradient(135deg, color-mix(in srgb, ${soft} 90%, ${base}), color-mix(in srgb, ${deep} 26%, ${base}))` };
    case 'aurora':
      return {
        background: `radial-gradient(60% 90% at 6% 0%, color-mix(in srgb, ${deep} 38%, transparent), transparent), radial-gradient(60% 90% at 100% 8%, rgba(122, 162, 255, 0.3), transparent), radial-gradient(70% 100% at 70% 115%, rgba(255, 122, 182, 0.28), transparent), ${base}`,
      };
    case 'dots':
      return { background: `radial-gradient(circle, ${faint(0.34)} 1.6px, transparent 1.8px) 0 0 / 14px 14px, ${wash}` };
    case 'stripes':
      return { background: `repeating-linear-gradient(135deg, ${faint(0.16)} 0 6px, transparent 6px 14px), ${wash}` };
    case 'grid':
      return { background: `linear-gradient(${faint(0.2)} 1px, transparent 1px) 0 0 / 16px 16px, linear-gradient(90deg, ${faint(0.2)} 1px, transparent 1px) 0 0 / 16px 16px, ${wash}` };
    case 'waves': {
      const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='48' height='14'><path d='M0 7 Q12 -1 24 7 T48 7' fill='none' stroke='${hex}' stroke-opacity='0.28' stroke-width='1.6'/></svg>`;
      return { background: `url("data:image/svg+xml,${encodeURIComponent(svg)}") 0 0 / 48px 14px, ${wash}` };
    }
    case 'paws':
      return { background: `${tile(hex, 0.2, PAW)}, ${wash}` };
    case 'stars':
      return { background: `${tile(hex, 0.24, STAR)}, ${wash}` };
    case 'hearts':
      return { background: `${tile(hex, 0.22, HEART)}, ${wash}` };
    case 'paper':
      return { background: `${grain(0.8, 0.09)}, ${wash}` };
    case 'linen':
      return {
        background: `repeating-linear-gradient(0deg, rgba(120, 100, 70, 0.07) 0 1px, transparent 1px 3px), repeating-linear-gradient(90deg, rgba(120, 100, 70, 0.07) 0 1px, transparent 1px 3px), ${grain(0.5, 0.06)}, ${wash}`,
      };
    default:
      return {};
  }
}

/** The backdrops that make a page background: the blurred photo is the card's own. */
export const PET_SCENES = PET_BACKDROPS.filter((b) => b.key !== 'photo');

/** The feed area's own background, from `scene`; none leaves the page as it is. */
export function petSceneStyle(look?: PetLook | null): CSSProperties {
  const key = look?.scene;
  return key && key !== 'plain' && key !== 'photo' ? { ...petBackdropStyle(key, petTintHex(look)) } : {};
}

/**
 * Ready looks: a whole mood in one tap (colour, face, frame, backdrops), to change piece by piece afterwards. The line under
 * the name is the owner's own and is not touched.
 */
export const PET_VIBES = [
  { key: 'cozy', label: 'Уют', look: { accent: 'sun', font: 'marck', frame: 'gallery', backdrop: 'linen', scene: 'paper', tint: '' } },
  { key: 'cute', label: 'Милота', look: { accent: 'rose', font: 'pacifico', frame: 'heart', backdrop: 'hearts', scene: 'dots', tint: '' } },
  { key: 'pastel', label: 'Пастель', look: { accent: 'lilac', font: 'bad', frame: 'pearl', backdrop: 'aurora', scene: 'fill', tint: 'sky' } },
  { key: 'retro', label: 'Ретро', look: { accent: 'sun', font: 'neucha', frame: 'film', backdrop: 'grid', scene: 'paper', tint: '' } },
  { key: 'neon', label: 'Неон', look: { accent: 'lilac', font: 'amatic', frame: 'neon', backdrop: 'aurora', scene: 'stars', tint: '' } },
  { key: 'space', label: 'Космос', look: { accent: 'lilac', font: 'amatic', frame: 'star', backdrop: 'stars', scene: 'gradient', tint: 'sky' } },
  { key: 'nature', label: 'Природа', look: { accent: 'sage', font: 'caveat', frame: 'flower', backdrop: 'waves', scene: 'linen', tint: '' } },
  { key: 'sea', label: 'Море', look: { accent: 'sky', font: 'pacifico', frame: 'porthole', backdrop: 'waves', scene: 'waves', tint: 'teal' } },
  { key: 'minimal', label: 'Минимал', look: { accent: 'slate', font: '', frame: 'polaroid', backdrop: 'plain', scene: 'plain', tint: '' } },
] as const;
