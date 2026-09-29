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
    root.classList.toggle('keyboard-open', open);
    root.style.setProperty('--keyboard-inset', open ? `${covered}px` : '0px');
  };

  viewport.addEventListener('resize', update);
  viewport.addEventListener('scroll', update);
  window.addEventListener('resize', update);
  document.addEventListener('focusin', update);
  // Focus moving from one field to the next passes through «nothing».
  document.addEventListener('focusout', () => setTimeout(update, 60));
  update();
}
