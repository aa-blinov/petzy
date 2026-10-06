import { useLayoutEffect } from 'react';
import { usePet } from '../hooks/usePet';
import { petAccentAttr, petLookOf, petSceneStyle } from '../utils/petLook';
import { usePetLookPreview } from '../utils/petLookPreview';

/**
 * Puts the selected pet's look on the whole app, not on one screen: its colour re-tints the accent and the backdrops, and
 * its scene is the background of every screen (`main` reads `--pet-scene-bg`). It is set on <body>, under <html>, where the
 * theme's own tones are chosen, so the pet's tones follow light and dark. While the look is being edited the draft is shown
 * in place of the saved one (utils/petLookPreview.ts). Another pet in the switcher, or none, and it is taken off.
 */
export function PetLookTheme() {
  const { getSelectedPet } = usePet();
  const preview = usePetLookPreview();
  const look = preview ?? petLookOf(getSelectedPet);
  const accent = petAccentAttr(look)['data-pet-accent'];
  const scene = petSceneStyle(look).background;

  // useLayoutEffect, not useEffect: the colour has to reach <body> before the browser
  // paints, or the first screen after opening the app came out in the plain page colour
  // and only then took the pet's own.
  useLayoutEffect(() => {
    const body = document.body;
    if (accent) body.setAttribute('data-pet-accent', accent);
    else body.removeAttribute('data-pet-accent');
    if (scene) body.style.setProperty('--pet-scene-bg', String(scene));
    else body.style.removeProperty('--pet-scene-bg');
    return () => {
      body.removeAttribute('data-pet-accent');
      body.style.removeProperty('--pet-scene-bg');
    };
  }, [accent, scene]);

  return null;
}
