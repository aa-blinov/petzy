import { useLayoutEffect } from 'react';
import { usePet } from '../hooks/usePet';
import { petAccentAttr, petLookOf, petSceneStyle } from '../utils/petLook';
import { usePetLookPreview } from '../utils/petLookPreview';

/**
 * The selected pet's scene is the background of every screen: `main` reads `--pet-scene-bg`, and it is set on <body>, under <html>, where the theme's own tones are chosen, so the pet's tones follow light and dark. While the look is being edited the draft is shown in place of the saved one (utils/petLookPreview.ts). Another pet in the switcher, or none, and it is taken off.
 *
 * The pet's colour is not set here. It used to be, on <body> too, which re-tinted every control under it: the chips, the segmented switches, the dose widget and the FAB all read `--app-accent-soft` and `--app-accent-deep`, so a pet with a sage coat turned the buttons green. The pet card and the pet's chip in the switcher already carry `data-pet-accent` on themselves, which is where the colour belongs: a pet's coat is that pet's, and not the app's buttons.
 */
export function PetLookTheme() {
  const { getSelectedPet } = usePet();
  const preview = usePetLookPreview();
  const look = preview ?? petLookOf(getSelectedPet);
  const scene = petSceneStyle(look).background;

  // useLayoutEffect, not useEffect: the background has to reach <body> before the browser
  // paints, or the first screen after opening the app came out in the plain page colour
  // and only then took the pet's own.
  useLayoutEffect(() => {
    const body = document.body;
    if (scene) body.style.setProperty('--pet-scene-bg', String(scene));
    else body.style.removeProperty('--pet-scene-bg');
    return () => {
      body.style.removeProperty('--pet-scene-bg');
    };
  }, [scene]);

  // The pet's own tones, for the screen behind the records (globals.css, body[data-pet-scene-accent]). The attribute is
  // only the name of the colour: the tones themselves live in the stylesheet, next to the card's.
  const accent = petAccentAttr(look)['data-pet-accent'];
  useLayoutEffect(() => {
    const body = document.body;
    if (accent) body.setAttribute('data-pet-scene-accent', accent);
    else body.removeAttribute('data-pet-scene-accent');
    return () => {
      body.removeAttribute('data-pet-scene-accent');
    };
  }, [accent]);

  return null;
}
