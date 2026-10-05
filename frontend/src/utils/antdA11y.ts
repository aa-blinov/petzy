/**
 * Keyboard and screen-reader access for antd-mobile's clickable rows.
 *
 * A clickable List.Item (and every Form.Item with `clickable`, which is
 * how all the date, species and sex pickers open) renders as an `<a>`
 * with no href: not in the Tab order, not announced as a control, and
 * deaf to Enter. List.Item forwards tabIndex and aria-* props but not
 * `role` or key handlers, so patching each call site can't finish the
 * job. ActionSheet choices (the row actions menu) are built the same
 * way. This fixes every such element in one place instead:
 *
 *   - rows get role="button" and tabindex=0 as they mount
 *     (disabled rows get aria-disabled and stay out of the Tab order);
 *   - Enter or Space on a patched row clicks it, as on a real button;
 *   - form labels are linked to their fields (see linkLabel);
 *   - an open sheet or dialog is a modal: the page behind it is hidden from a screen reader, Tab stays inside the sheet (and starts
 *     in it when the person was using the keyboard), and the focus goes back to what opened it when it closes;
 *   - the row menu (an ActionSheet) is a dialog named «Действия», and its «Отмена» is no `option` of a list that is not there
 *     (the wrapper keeps no role: the button inside it is the control);
 *   - the clear «×» of a text field, a `<div>` with an aria-label and no role (an attribute ARIA forbids there), becomes a
 *     named button that stays out of the Tab order: whoever types can erase with the keyboard, so it is no second stop.
 */

const ROW_SELECTOR = 'a.adm-list-item:not([href]), a.adm-action-sheet-button-item:not([href])';
const PATCHED = 'data-a11y-row';

const EDITABLE = 'input:not([readonly]):not([disabled]):not([type="hidden"]), textarea:not([readonly]), select';

function patch(row: Element) {
  if (row.hasAttribute(PATCHED)) return;
  row.setAttribute(PATCHED, '');
  // A row wrapping a real text field (FormDefaults' free-text rows) is
  // not a button: the field is the control and already takes focus.
  if (row.querySelector(EDITABLE)) return;
  // A picker row shows its value in a read-only input; that input would
  // be a second, dead Tab stop right after the row itself.
  row.querySelectorAll('input[readonly], textarea[readonly]').forEach((el) => el.setAttribute('tabindex', '-1'));
  row.setAttribute('role', 'button');
  const disabled =
    row.classList.contains('adm-list-item-disabled') || row.classList.contains('adm-action-sheet-button-item-disabled');
  row.setAttribute('tabindex', disabled ? '-1' : '0');
  if (disabled) row.setAttribute('aria-disabled', 'true');
}

let fieldSeq = 0;

// Form.Item only points its <label for> at the field when antd's own
// form store owns it; these forms use react-hook-form, so every label
// was unattached and fields were announced by placeholder alone. Link
// each label to the text field inside its item, and mark it required
// when antd drew the asterisk.
function linkLabel(item: Element) {
  if (item.hasAttribute('data-a11y-label')) return;
  item.setAttribute('data-a11y-label', '');
  const label = item.querySelector<HTMLLabelElement>('label.adm-form-item-label');
  const field = item.querySelector<HTMLElement>(EDITABLE);
  if (!label || !field) return;
  if (!field.id) field.id = `form-field-${++fieldSeq}`;
  if (!label.htmlFor) label.htmlFor = field.id;
  if (label.querySelector('.adm-form-item-required-asterisk')) field.setAttribute('aria-required', 'true');
}

const CLEAR_SELECTOR = '.adm-input-clear:not([role])';

function patchClear(el: Element) {
  el.setAttribute('role', 'button');
  el.setAttribute('tabindex', '-1');
}

// The menu of a row (Изменить, Удалить, Отмена): antd marks the wrapper of «Отмена» as an `option` with no listbox around it, which
// holds a button, and draws the sheet outside every landmark.
function patchActionSheet(sheet: Element) {
  sheet.querySelectorAll('.adm-action-sheet-cancel[role="option"]').forEach((el) => {
    el.removeAttribute('role');
    el.removeAttribute('aria-label');
  });
  const body = sheet.querySelector('.adm-popup-body');
  if (body && !body.hasAttribute('role')) {
    body.setAttribute('role', 'dialog');
    body.setAttribute('aria-label', 'Действия');
  }
}

function patchWithin(root: ParentNode) {
  if (root instanceof Element && root.matches('.adm-action-sheet-popup')) patchActionSheet(root);
  root.querySelectorAll('.adm-action-sheet-popup').forEach(patchActionSheet);
  if (root instanceof Element && root.matches(CLEAR_SELECTOR)) patchClear(root);
  root.querySelectorAll(CLEAR_SELECTOR).forEach(patchClear);
  if (root instanceof Element && root.matches(ROW_SELECTOR)) patch(root);
  root.querySelectorAll(ROW_SELECTOR).forEach(patch);
  if (root instanceof Element && root.matches('.adm-form-item')) linkLabel(root);
  root.querySelectorAll('.adm-form-item').forEach(linkLabel);
}

// `.app-modal`: a full-screen layer of the app's own (the PDF viewer of the Documents), a dialog like a sheet is.
const MODAL = '.adm-popup, .adm-center-popup, .app-modal';
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';

const isShown = (el: HTMLElement) => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
const shownModals = () => Array.from(document.querySelectorAll<HTMLElement>(MODAL)).filter(isShown);
const focusablesIn = (modal: HTMLElement) => Array.from(modal.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(isShown);

let usingKeyboard = false;
let opener: HTMLElement | null = null;

// Called as the page changes: the first sheet that opens hides the page behind it, the last one that closes shows it again.
function syncModal() {
  const root = document.getElementById('root');
  if (!root) return;
  const modals = shownModals();
  if (modals.length > 0) {
    if (root.getAttribute('aria-hidden') === 'true') return;
    opener = document.activeElement instanceof HTMLElement && document.activeElement !== document.body ? document.activeElement : null;
    root.setAttribute('aria-hidden', 'true');
    if (usingKeyboard) {
      const top = modals[modals.length - 1];
      (focusablesIn(top)[0] ?? top).focus({ preventScroll: true });
    }
  } else if (root.hasAttribute('aria-hidden')) {
    root.removeAttribute('aria-hidden');
    if (usingKeyboard && opener && document.contains(opener)) opener.focus({ preventScroll: true });
    opener = null;
  }
}

export function installAntdA11y() {
  patchWithin(document);

  let queued = false;
  const queueModalSync = () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      syncModal();
    });
  };
  // A sheet is shown and hidden by its class and style, and added to and taken from the body.
  new MutationObserver(queueModalSync).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['style', 'class'] });
  document.addEventListener('pointerdown', () => { usingKeyboard = false; }, true);
  document.addEventListener('keydown', (e) => {
    usingKeyboard = true;
    if (e.key !== 'Tab') return;
    const modals = shownModals();
    if (modals.length === 0) return;
    const top = modals[modals.length - 1];
    const items = focusablesIn(top);
    if (items.length === 0) {
      e.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement;
    if (!top.contains(active)) {
      e.preventDefault();
      first.focus();
    } else if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
  }, true);

  new MutationObserver((mutations) => {
    for (const m of mutations) {
      m.addedNodes.forEach((node) => {
        if (node instanceof Element) patchWithin(node);
      });
    }
  }).observe(document.body, { childList: true, subtree: true });

  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter' && e.key !== ' ') return;
    const target = e.target;
    if (!(target instanceof HTMLElement) || !target.hasAttribute(PATCHED)) return;
    if (target.getAttribute('aria-disabled') === 'true') return;
    // Space would otherwise scroll the page.
    e.preventDefault();
    target.click();
  });
}
