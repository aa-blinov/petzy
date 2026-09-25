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
 *   - form labels are linked to their fields (see linkLabel).
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

function patchWithin(root: ParentNode) {
  if (root instanceof Element && root.matches(ROW_SELECTOR)) patch(root);
  root.querySelectorAll(ROW_SELECTOR).forEach(patch);
  if (root instanceof Element && root.matches('.adm-form-item')) linkLabel(root);
  root.querySelectorAll('.adm-form-item').forEach(linkLabel);
}

export function installAntdA11y() {
  patchWithin(document);

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
