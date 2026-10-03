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

export interface PetLook {
  tagline?: string;
  accent?: string;
  /** A key of PET_FONTS: the hand-written face of the name on the card. */
  font?: string;
  /** A key of PET_FRAMES: the frame around the photo (or the species picture) on the card. */
  frame?: string;
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
  { key: 'arch', label: 'Арка' },
  { key: 'flower', label: 'Цветок' },
  { key: 'circle', label: 'Круг' },
] as const;

export function petFrameOf(look?: PetLook | null): (typeof PET_FRAMES)[number] | undefined {
  return PET_FRAMES.find((f) => f.key === look?.frame);
}

// Eight petals round a centre, one mask: the photo takes the shape of a flower.
const FLOWER_MASK = `url("data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><g fill='#000'><circle cx='50' cy='50' r='33'/>${Array.from({ length: 8 }, (_, i) => {
    const a = (i * Math.PI) / 4;
    return `<circle cx='${(50 + 31 * Math.cos(a)).toFixed(1)}' cy='${(50 + 31 * Math.sin(a)).toFixed(1)}' r='19'/>`;
  }).join('')}</g></svg>`,
)}")`;

export interface PetFrameStyle {
  /** On the box that holds the picture; it keeps its size: shadows and rotation draw outside it, borders sit inside it. */
  box: CSSProperties;
  /** On the photo inside, where the box's own rounding is not enough. */
  image?: CSSProperties;
}

/**
 * What a frame adds to the picture, drawn in CSS only. `scale` shrinks the widths for the small samples in the picker.
 * The neon takes the pet's colour, so it follows the accent chosen next to it; the others have colours of their own.
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
    case 'arch':
      return { box: { borderRadius: `50% 50% ${px(10)} ${px(10)} / 42% 42% ${px(10)} ${px(10)}` } };
    case 'flower':
      return {
        box: {
          borderRadius: 0,
          background: 'transparent',
          WebkitMaskImage: FLOWER_MASK,
          maskImage: FLOWER_MASK,
          WebkitMaskSize: '100% 100%',
          maskSize: '100% 100%',
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
        },
      };
    case 'circle':
      return { box: { borderRadius: '50%' } };
    default:
      return { box: {} };
  }
}
