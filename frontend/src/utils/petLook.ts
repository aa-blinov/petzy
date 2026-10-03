/**
 * How a pet's card shows it: a short line about the pet and a colour from a fixed palette.
 *
 * The colours are only names here; the tints are in globals.css (`[data-pet-accent]`), light and dark, each checked at
 * 5:1 or better for its deep tone on its soft one. The server knows the same names (PET_ACCENTS in web/schemas.py).
 */

import type { Pet } from '../services/pets.service';

export const PET_TAGLINE_MAX = 40;

export interface PetLook {
  tagline?: string;
  accent?: string;
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
