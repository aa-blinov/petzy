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

export function petLookOf(pet: Pick<Pet, 'look'>): PetLook {
  return pet.look ?? {};
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

export const PET_FRAMES = [
  { key: 'story', label: 'Сторис' },
  { key: 'sticker', label: 'Стикер' },
  { key: 'neon', label: 'Неон' },
  { key: 'holo', label: 'Голограмма' },
  { key: 'polaroid', label: 'Полароид' },
  { key: 'gallery', label: 'Галерея' },
  { key: 'porthole', label: 'Иллюминатор' },
  { key: 'film', label: 'Плёнка' },
  { key: 'stamp', label: 'Марка' },
  { key: 'popart', label: 'Поп-арт' },
  { key: 'glitch', label: 'Глитч' },
  { key: 'aura', label: 'Аура' },
  { key: 'arch', label: 'Арка' },
  { key: 'circle', label: 'Круг' },
  { key: 'flower', label: 'Цветок' },
  { key: 'heart', label: 'Сердце' },
  { key: 'star', label: 'Звезда' },
  { key: 'cloud', label: 'Облако' },
  { key: 'paw', label: 'Лапка' },
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
  star: `<polygon fill='#000' points='${Array.from({ length: 32 }, (_, i) => {
    const a = (i * Math.PI) / 16 - Math.PI / 2;
    const r = i % 2 === 0 ? 49 : 41;
    return `${(50 + r * Math.cos(a)).toFixed(1)},${(50 + r * Math.sin(a)).toFixed(1)}`;
  }).join(' ')}'/>`,
  cloud: `<g fill='#000'><circle cx='27' cy='63' r='19'/><circle cx='47' cy='42' r='25'/><circle cx='72' cy='50' r='21'/><circle cx='50' cy='67' r='24'/><circle cx='77' cy='69' r='17'/></g>`,
  // A big pad and four toes.
  paw: `<g fill='#000'><ellipse cx='50' cy='69' rx='28' ry='23'/><ellipse cx='19' cy='44' rx='11' ry='15' transform='rotate(-22 19 44)'/><ellipse cx='39' cy='23' rx='11' ry='15' transform='rotate(-7 39 23)'/><ellipse cx='61' cy='23' rx='11' ry='15' transform='rotate(7 61 23)'/><ellipse cx='81' cy='44' rx='11' ry='15' transform='rotate(22 81 44)'/></g>`,
  // A postage stamp: paper with a perforated edge.
  stamp: `<mask id='m'><rect width='100' height='100' fill='#fff'/><g fill='#000'>${Array.from({ length: 10 }, (_, i) => {
    const c = 5 + i * 10;
    return `<circle cx='${c}' cy='0' r='3.2'/><circle cx='${c}' cy='100' r='3.2'/><circle cx='0' cy='${c}' r='3.2'/><circle cx='100' cy='${c}' r='3.2'/>`;
  }).join('')}</g></mask><rect width='100' height='100' fill='#000' mask='url(#m)'/>`,
};

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
          background: '#fff',
          boxShadow: '0 3px 10px rgba(0, 0, 0, 0.28)',
          transform: 'rotate(-3deg)',
        },
      };
    case 'gallery':
      // A wooden frame with a cream mat, as hung in a gallery.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(5)} solid transparent`,
          padding: px(5),
          borderRadius: px(2),
          background:
            'linear-gradient(#f4efe6, #f4efe6) padding-box, linear-gradient(135deg, #6b4a2b, #a67c52, #5a3d22, #8f6a43) border-box',
          boxShadow: '0 3px 8px rgba(0, 0, 0, 0.35)',
        },
      };
    case 'porthole':
      // A ship's porthole: a round window in a ring of metal.
      return {
        box: {
          boxSizing: 'border-box',
          border: `${px(6)} solid transparent`,
          borderRadius: '50%',
          background:
            'linear-gradient(#0b2a3c, #0b2a3c) padding-box, linear-gradient(145deg, #f5f7fa, #9aa7b5 40%, #e8edf2 60%, #6f7c8a) border-box',
          boxShadow: '0 3px 8px rgba(0, 0, 0, 0.35)',
        },
      };
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
