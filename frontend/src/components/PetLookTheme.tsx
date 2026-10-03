import { useEffect } from 'react';
import { usePet } from '../hooks/usePet';
import { petAccentAttr, petLookOf, petSceneStyle, petTintAttr } from '../utils/petLook';

/**
 * Puts the selected pet's look on the whole app, not on one screen: its colour re-tints the accent, its tint colours the
 * backdrops, and its scene is the background of every page (`.page-container` reads `--pet-scene-bg`). It is set on
 * <body>, under <html>, where the theme's own tones are chosen, so the pet's tones follow light and dark. Another pet in the
 * switcher, or none, and it is taken off again.
 */
export function PetLookTheme() {
  const { getSelectedPet } = usePet();
  const look = petLookOf(getSelectedPet);
  const accent = petAccentAttr(look)['data-pet-accent'];
  const tint = petTintAttr(look)['data-pet-tint'];
  const scene = petSceneStyle(look).background;

  useEffect(() => {
    const body = document.body;
    const set = (name: string, value: string | undefined) => (value ? body.setAttribute(name, value) : body.removeAttribute(name));
    set('data-pet-accent', accent);
    set('data-pet-tint', tint);
    if (scene) body.style.setProperty('--pet-scene-bg', String(scene));
    else body.style.removeProperty('--pet-scene-bg');
    return () => {
      body.removeAttribute('data-pet-accent');
      body.removeAttribute('data-pet-tint');
      body.style.removeProperty('--pet-scene-bg');
    };
  }, [accent, tint, scene]);

  return null;
}
