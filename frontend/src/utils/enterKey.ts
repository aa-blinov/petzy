/**
 * The Return key of a phone keyboard, in every form, in one place.
 *
 * The keys did nothing useful: on most forms Enter did not move on and did
 * not submit, and on sign-in it submitted from the very first field (an
 * error about the empty password instead of going to the password). Now
 *
 *   - on every text field but the last the key reads «Далее» and moves
 *     focus to the next field, keeping the keyboard up;
 *   - on the last field it reads «Перейти» and presses the form's main
 *     button, if that button is marked `data-enter-submit` (sign-in,
 *     password and email forms: short, one purpose);
 *   - on the last field of any other form it reads «Готово» and closes the
 *     keyboard: a long form (a medicine, a pet) mustn't be saved by an
 *     accidental Return;
 *   - a multi-line field keeps Enter as a new line.
 *
 * A field that already has its own `enterkeyhint` (the pet-name field on
 * onboarding handles Enter itself) is left alone.
 */

const AUTO = 'data-enter-auto';
const NON_TEXT_INPUTS = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'file', 'range', 'color', 'image', 'hidden']);
// The screen (or the dialog on it) the field belongs to. Not the nearest
// <form>: a screen's fields and its main button often sit in different ones
// (or the button outside any), and the natural order is the one on screen.
const GROUP_SELECTOR = '[role="dialog"], .adm-popup, .adm-modal, .adm-dialog-wrap, main';

type TextField = HTMLInputElement | HTMLTextAreaElement;

function isEditable(el: Element): el is TextField {
  if (el instanceof HTMLTextAreaElement) return !el.readOnly && !el.disabled;
  if (!(el instanceof HTMLInputElement)) return false;
  return !el.readOnly && !el.disabled && !NON_TEXT_INPUTS.has(el.type);
}

function isVisible(el: HTMLElement): boolean {
  return el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
}

function groupOf(el: Element): Element {
  return el.closest(GROUP_SELECTOR) ?? document.body;
}

function fieldsIn(group: Element): TextField[] {
  return [...group.querySelectorAll('input, textarea')].filter(
    (el): el is TextField => isEditable(el) && isVisible(el) && el.tabIndex !== -1,
  );
}

function submitButtonIn(group: Element): HTMLButtonElement | null {
  const button = group.querySelector<HTMLButtonElement>('[data-enter-submit]');
  if (!button || button.disabled || button.getAttribute('aria-disabled') === 'true') return null;
  return button;
}

function nextField(el: TextField): TextField | null {
  const fields = fieldsIn(groupOf(el));
  const at = fields.indexOf(el);
  return at >= 0 && at < fields.length - 1 ? fields[at + 1] : null;
}

/** What the Return key should read on this field. */
function hintFor(el: TextField): 'next' | 'go' | 'done' {
  if (nextField(el)) return 'next';
  return groupOf(el).querySelector('[data-enter-submit]') ? 'go' : 'done';
}

function ownedByPage(el: TextField): boolean {
  return el.hasAttribute('enterkeyhint') && !el.hasAttribute(AUTO);
}

function refreshHint(el: TextField) {
  if (el instanceof HTMLTextAreaElement || ownedByPage(el)) return;
  const hint = hintFor(el);
  if (el.getAttribute('enterkeyhint') !== hint) el.setAttribute('enterkeyhint', hint);
  el.setAttribute(AUTO, '');
}

function refreshAll() {
  document.querySelectorAll('input, textarea').forEach((el) => {
    if (isEditable(el) && isVisible(el)) refreshHint(el);
  });
}

export function installEnterKey() {
  let scheduled = 0;
  const schedule = () => {
    if (scheduled) return;
    scheduled = requestAnimationFrame(() => {
      scheduled = 0;
      refreshAll();
    });
  };
  new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
  document.addEventListener('focusin', (event) => {
    if (event.target instanceof Element && isEditable(event.target)) refreshHint(event.target);
  });

  // Capture phase: before antd's Form turns Enter into a submit.
  document.addEventListener(
    'keydown',
    (event) => {
      if (event.key !== 'Enter' || event.isComposing || event.shiftKey || event.altKey || event.ctrlKey || event.metaKey) return;
      const el = event.target;
      // A text area keeps Enter for the new line; the page owns its own fields.
      if (!(el instanceof HTMLInputElement) || !isEditable(el) || ownedByPage(el)) return;

      const next = nextField(el);
      if (next) {
        event.preventDefault();
        event.stopPropagation();
        next.focus();
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      const submit = submitButtonIn(groupOf(el));
      if (submit) submit.click();
      else el.blur();
    },
    true,
  );
  schedule();
}
