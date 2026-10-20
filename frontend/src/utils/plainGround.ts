import { useLayoutEffect } from 'react';

/**
 * A document on a plain desk. The pet's scene is the background of every screen of the app, but
 * the medical card is a record: it is read, not looked at, and the pattern of the feed under it
 * only makes the sheet harder to read. While the card is open the ground is the plain page
 * colour; when the card closes, the pet's scene comes back.
 *
 * The scene is set on <body> by PetLookTheme, as an inline style, so the plain ground is asked
 * for with a mark on <body> and a rule in the stylesheet (globals.css): the rule is marked
 * important, because the chosen pet may change under the card and the theme will then set the
 * scene again, over an ordinary declaration.
 */
export function usePlainGround() {
  // useLayoutEffect, not useEffect: the ground has to change before the browser paints, or the
  // card comes out on the pet's pattern for a frame and then jumps to the plain one.
  useLayoutEffect(() => {
    const body = document.body;
    body.setAttribute('data-plain-ground', 'medical-card');
    return () => {
      body.removeAttribute('data-plain-ground');
    };
  }, []);
}
