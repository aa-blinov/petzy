/**
 * The on-screen keyboard, seen from the page.
 *
 * On iPhone (and Android Chrome) the keyboard doesn't resize the page: it
 * covers the bottom of it, and only the *visual* viewport shrinks. Fixed
 * elements stay where they were, behind the keyboard, and the last field
 * of a form can be scrolled no higher than the page's own end, still under
 * the keys. While a text field has focus and the visual viewport is at
 * least 120px shorter than the page, this marks <html> with `keyboard-open`
 * and `--keyboard-inset` (how much the keyboard covers), so the styles can
 * give the page that room and take the tab bar and the add button out of
 * the way (they can't be pressed under the keys, and on browsers that
 * shrink the page instead they'd sit on top of the keyboard).
 */

const NON_TEXT_INPUTS = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'range', 'color', 'image', 'hidden']);
const MIN_KEYBOARD_PX = 120;

function isTextField(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  if (el instanceof HTMLTextAreaElement) return !el.readOnly;
  if (el instanceof HTMLInputElement) return !el.readOnly && !NON_TEXT_INPUTS.has(el.type);
  return el.isContentEditable;
}

export function installKeyboardWatch() {
  const viewport = window.visualViewport;
  if (!viewport) return;
  const root = document.documentElement;
  // The tallest the page has been at this width: what «no keyboard» is.
  let tallest = window.innerHeight;
  let width = window.innerWidth;

  const update = () => {
    if (window.innerWidth !== width) {
      // Rotated or resized: what was tall is no longer.
      width = window.innerWidth;
      tallest = window.innerHeight;
    }
    tallest = Math.max(tallest, window.innerHeight);
    const covered = Math.round(tallest - (viewport.offsetTop + viewport.height));
    const open = isTextField(document.activeElement) && covered >= MIN_KEYBOARD_PX;
    // Some browsers shrink the page itself instead: fixed elements are then
    // already above the keys, and only what is anchored to the page's own
    // bottom (the padding) needs the room.
    const pageShrunk = tallest - window.innerHeight >= MIN_KEYBOARD_PX;
    // iPhone, a standalone app: after the keyboard is gone (or the app was left and returned to) the visual viewport
    // can stay panned down inside the page, and everything fixed to the bottom floats that far above the screen's
    // edge. While there is no keyboard and no pinch-zoom, the fixed bars are moved down by that offset; the
    // page is also nudged once, which makes the browser put the viewport back where it belongs.
    const offset = Math.max(0, Math.round(viewport.offsetTop));
    let panned = !open && viewport.scale <= 1.01 ? offset : 0;
    // But only as far as the bar actually floats. The nudge above cannot always put the viewport back
    // (at the end of the page there is nowhere to go, and a slight pinch-zoom leaves it panned too),
    // and a stale offset is not a harmless leftover: a bottom-fixed bar moved down by it leaves the
    // screen altogether, which is the bar «улетающий» вниз. So the bar may come down to the edge of
    // the visible area and not one pixel past it.
    const bar = document.querySelector('.bottom-tab-bar-container');
    if (bar && panned) {
      root.style.setProperty('--vv-shift', '0px'); // its unshifted place, read before shifting again
      const floats = Math.round(viewport.offsetTop + viewport.height - bar.getBoundingClientRect().bottom);
      panned = Math.min(panned, Math.max(0, floats));
    }
    root.style.setProperty('--vv-shift', `${panned}px`);
    if (panned > 0 && !isTextField(document.activeElement)) {
      window.requestAnimationFrame(() => window.scrollTo(window.scrollX, window.scrollY));
    }
    root.classList.toggle('keyboard-open', open);
    root.style.setProperty('--keyboard-inset', open ? `${covered}px` : '0px');
    // How far up a bar fixed to the bottom must sit to clear the keyboard.
    root.style.setProperty('--keyboard-fixed-offset', open && !pageShrunk ? `${covered}px` : '0px');
  };

  viewport.addEventListener('resize', update);
  viewport.addEventListener('scroll', update);
  window.addEventListener('resize', update);
  document.addEventListener('focusin', update);
  // Focus moving from one field to the next passes through «nothing».
  document.addEventListener('focusout', () => setTimeout(update, 60));
  update();
}
