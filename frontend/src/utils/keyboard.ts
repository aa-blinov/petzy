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
  // What is written on <html> now: a write of the same value still makes the browser restyle the whole page, and
  // this runs on every scroll frame.
  let shift = 0;
  // The keyboard has been open: what is left of it after it closes is a leftover to undo.

  // A pan left by the keyboard stays a leftover until the viewport actually comes home: iOS can keep
  // reporting it after the page it belonged to is gone (a form closed by a navigation), and one clean
  // update is not enough. Without this the next scroll reported the same pan again and the bars went
  // off once more, which is precisely the bug the person reported.
  let panLeftover = false;
  // The header's own shift. Chrome on iPhone collapses its toolbar as the page is read, and that
  // moves the visual viewport once and reports it as a scroll, not as a resize: the layout viewport
  // stays where it was, so a fixed header ends up above the visible area, under the clock (Chromium
  // issues 504094431 and 417426570). The pan is followed, but only once it has stopped changing: the
  // spring-back at the end of a page reports a pan for a moment, and following that would make the
  // header jump. 90ms is longer than a spring-back and shorter than a finger's pause.
  let shiftTop = 0;
  let topTimer = 0;
  const written = new Map<string, string>();
  const write = (name: string, value: string) => {
    if (written.get(name) === value) return;
    written.set(name, value);
    root.style.setProperty(name, value);
  };

  // `scrolling`: called from a scroll of the visual viewport. On iPhone the end of a page springs back, and while it
  // does the visual viewport reports an offset for a moment; moving the bars by it then (and nudging the page) made
  // the tab bar jump at the bottom of every page and broke the momentum. A scroll may only take a shift away; only a
  // resize, a focus change or a return to the app may put one in. The exception is a field being typed in (below).
  const update = (scrolling = false) => {
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
    // edge. While there is no pinch-zoom, the fixed bars are moved down by that offset; the page is also nudged once,
    // which makes the browser put the viewport back where it belongs. A field being typed in is no exception: iOS pans
    // the visual viewport to show the field, and a fixed top bar left in place floats out of the screen by that much.
    // The tab bar and the add button are hidden while the keyboard is up, so only the header follows then.
    const offset = Math.max(0, Math.round(viewport.offsetTop));
    let panned = viewport.scale <= 1.01 ? offset : 0;
    // A pan that outlives the page that made it is a leftover, not a place. iOS keeps the visual
    // viewport where the keyboard left it when a form is closed by a navigation: the field
    // disappears with the page, no focusout ever comes, and following that pan dragged both bars off
    // the screen (the tab bar away from the bottom edge, the header under the notch). The leftover is
    // set by the navigation itself (below), and it holds until the viewport comes home, so a later
    // scroll cannot pick the same stale pan up again. A pan with no navigation behind it — Chrome's
    // own toolbar, the app returning from the background — is real and is followed as before.
    if (panLeftover && offset === 0) panLeftover = false;
    if (panLeftover) panned = 0;
    const leftover = panLeftover;
    // But only as far as the bar actually floats. The nudge above cannot always put the viewport back
    // (at the end of the page there is nowhere to go, and a slight pinch-zoom leaves it panned too),
    // and a stale offset is not a harmless leftover: a bottom-fixed bar moved down by it leaves the
    // screen altogether, which is the bar «улетающий» вниз. So the bar may come down to the edge of
    // the visible area and not one pixel past it.
    // Only without a field being typed in: the keyboard is then coming up or going down, and the pan that comes with it
    // is real, not a spring-back.
    if (scrolling && !isTextField(document.activeElement)) panned = Math.min(panned, shift);
    const bar = document.querySelector('.bottom-tab-bar-container');
    // The tab bar is hidden while the keyboard is up, so only a bar that is shown is kept on the screen.
    if (bar && panned && !open) {
      write('--vv-shift', '0px'); // its unshifted place, read before shifting again
      const floats = Math.round(viewport.offsetTop + viewport.height - bar.getBoundingClientRect().bottom);
      panned = Math.min(panned, Math.max(0, floats));
    }
    shift = panned;
    write('--vv-shift', `${panned}px`);
    // The header, on its own: at once when nothing is scrolling (the keyboard coming up, the app
    // returning), and after the pan settles when the page is being read.
    const topWanted = viewport.scale <= 1.01 && !panLeftover ? offset : 0;
    if (!scrolling) {
      window.clearTimeout(topTimer);
      shiftTop = topWanted;
      write('--vv-shift-top', `${shiftTop}px`);
    } else if (topWanted !== shiftTop) {
      window.clearTimeout(topTimer);
      topTimer = window.setTimeout(() => {
        shiftTop = topWanted;
        write('--vv-shift-top', `${shiftTop}px`);
      }, 90);
    }
    if (panned > 0 && !scrolling && !isTextField(document.activeElement)) {
      window.requestAnimationFrame(() => window.scrollTo(window.scrollX, window.scrollY));
    }
    // Same coordinates do nothing on iOS, so the page moves by a pixel and back: that is the nudge
    // the browser answers by putting the visual viewport home.
    if (leftover && !scrolling) {
      window.requestAnimationFrame(() => {
        const x = window.scrollX;
        const y = window.scrollY;
        window.scrollTo(x, Math.max(0, y - 1));
        window.scrollTo(x, y);
      });
    }
    if (root.classList.contains('keyboard-open') !== open) root.classList.toggle('keyboard-open', open);
    write('--keyboard-inset', open ? `${covered}px` : '0px');
    // How far up a bar fixed to the bottom must sit to clear the keyboard.
    write('--keyboard-fixed-offset', open && !pageShrunk ? `${covered}px` : '0px');
  };

  const full = () => update(false);
  viewport.addEventListener('resize', full);
  viewport.addEventListener('scroll', () => update(true));
  window.addEventListener('resize', full);
  document.addEventListener('focusin', full);
  // Focus moving from one field to the next passes through «nothing».
  document.addEventListener('focusout', () => setTimeout(full, 60));
  // Back from another app: this is when the viewport is left panned without any resize.
  window.addEventListener('pageshow', full);
  // A route change can take the field away without a focusout (a form closed by navigation), so
  // the bars are re-read whenever the page is not the one they were read on.
  window.addEventListener('popstate', full);
  window.addEventListener('petzy:navigate', full);
  // A form is closed by a navigation, and its field goes with the page: no blur, no focusout, and iOS
  // keeps the visual viewport where the keyboard left it. A pan that outlives the page that made it
  // is a leftover, not a place, so the bars come home and the page is nudged once. A pan with no
  // navigation behind it is real (Chrome's own toolbar, the app returning from the background) and
  // is followed as before.
  const dropLeftover = () => {
    if (viewport.offsetTop <= 0 || isTextField(document.activeElement)) return;
    panLeftover = true;
    full();
    window.requestAnimationFrame(() => {
      const x = window.scrollX;
      const y = window.scrollY;
      window.scrollTo(x, Math.max(0, y - 1));
      window.scrollTo(x, y);
    });
  };
  window.addEventListener('popstate', dropLeftover);
  window.addEventListener('petzy:navigate', dropLeftover);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') setTimeout(full, 60);
  });
  full();
}
