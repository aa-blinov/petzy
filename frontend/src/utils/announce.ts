/**
 * Screen-reader announcements.
 *
 * antd-mobile's Toast renders a plain div with no role, so "Запись
 * сохранена" or a failed login appeared on screen and was never read
 * aloud. Two visually hidden live regions (polite for confirmations,
 * assertive for failures) live at the end of <body>; announce() writes
 * the message into one of them.
 */

type Politeness = 'polite' | 'assertive';

const regions: Partial<Record<Politeness, HTMLElement>> = {};

function region(politeness: Politeness): HTMLElement {
  let el = regions[politeness];
  if (!el || !el.isConnected) {
    el = document.createElement('div');
    el.className = 'sr-only';
    el.setAttribute('aria-live', politeness);
    el.setAttribute('aria-atomic', 'true');
    // role=alert makes the assertive region interrupt on older VoiceOver
    // builds that ignore aria-live on nodes created after page load.
    el.setAttribute('role', politeness === 'assertive' ? 'alert' : 'status');
    document.body.appendChild(el);
    regions[politeness] = el;
  }
  return el;
}

export function announce(message: string, politeness: Politeness = 'polite') {
  const el = region(politeness);
  // Clear first, then write on the next frame: setting the same text
  // twice in a row ("Сохранено", "Сохранено") is not a change, so the
  // second one would stay silent.
  el.textContent = '';
  requestAnimationFrame(() => {
    el.textContent = message;
  });
}
