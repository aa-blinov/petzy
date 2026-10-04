import { useEffect, useMemo, useRef, useState } from 'react';
import { Popup, SearchBar, type SearchBarRef } from 'antd-mobile';

import { DraggableSheetBody } from './DraggableSheetBody';
import './ProductPickerSheet.css';

export interface ProductGroup {
  key: string;
  label: string;
  /** What it covers, when the label does not say. */
  detail?: string;
  items: string[];
}

const norm = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();

/**
 * One list to search, for a vaccine or a treatment: a field to type in, the names that fit below it, grouped by what they are
 * against; a name that is not on the list is used as it was typed. What the pet had before comes first. It is a dropdown with
 * a search, not a row of chips: the person writes the name, the list only helps.
 */
export function ProductPickerSheet({
  visible,
  title,
  placeholder,
  groups,
  earlier,
  loading = false,
  failed = false,
  onRetry,
  onClose,
  onPick,
}: {
  visible: boolean;
  title: string;
  placeholder: string;
  groups: ProductGroup[];
  /** The names this pet already has, newest first. */
  earlier: string[];
  loading?: boolean;
  failed?: boolean;
  onRetry?: () => void;
  onClose: () => void;
  /** `group` is the key of the group a listed name is in, null for a name typed by hand. */
  onPick: (name: string, group: string | null) => void;
}) {
  const [query, setQuery] = useState('');
  const search = useRef<SearchBarRef>(null);
  const q = norm(query);

  // The cursor is in the field when the sheet has come up: the list is for whoever does not want to type it all.
  useEffect(() => {
    if (!visible) return;
    const timer = window.setTimeout(() => search.current?.focus(), 300);
    return () => window.clearTimeout(timer);
  }, [visible]);

  const shownEarlier = useMemo(() => earlier.filter((name) => !q || norm(name).includes(q)), [earlier, q]);
  const shown = useMemo(
    () =>
      groups
        .map((g) => {
          const groupMatches = !!q && (norm(g.label).includes(q) || norm(g.detail ?? '').includes(q));
          return { ...g, items: q && !groupMatches ? g.items.filter((name) => norm(name).includes(q)) : g.items };
        })
        .filter((g) => g.items.length > 0),
    [groups, q],
  );
  const exact = [...earlier, ...groups.flatMap((g) => g.items)].some((name) => norm(name) === q);
  const found = shownEarlier.length + shown.reduce((n, g) => n + g.items.length, 0);

  const finish = () => setQuery('');
  const close = () => {
    finish();
    onClose();
  };
  const pick = (name: string, group: string | null) => {
    finish();
    onPick(name, group);
  };
  // Enter takes the one name that fits, else what was typed.
  const enter = () => {
    const typed = query.trim();
    if (!typed) return;
    const only = shown.length === 1 && shown[0].items.length === 1 && shownEarlier.length === 0 ? { name: shown[0].items[0], group: shown[0].key } : null;
    if (only) pick(only.name, only.group);
    else pick(typed, null);
  };

  return (
    <Popup visible={visible} onMaskClick={close} position="bottom" bodyStyle={{ background: 'transparent' }}>
      <DraggableSheetBody visible={visible} onClose={close} maxHeight="85vh" label={title}>
        <h2 className="prodpick__title">{title}</h2>
        <div className="prodpick__search">
          <SearchBar ref={search} placeholder={placeholder} value={query} onChange={setQuery} onClear={() => setQuery('')} onSearch={enter} aria-label={title} />
        </div>

        {failed && (
          <p className="prodpick__note">
            Список не загрузился. Название можно вписать.{' '}
            {onRetry && (
              <button type="button" className="prodpick__link" onClick={onRetry}>
                Повторить
              </button>
            )}
          </p>
        )}
        {loading && !failed && <p className="prodpick__note">Загружаем список</p>}

        {shownEarlier.length > 0 && (
          <section className="prodpick__group" aria-label="Ранее">
            <h3 className="prodpick__group-title">Ранее у питомца</h3>
            <ul className="prodpick__list">
              {shownEarlier.map((name) => (
                <li key={name}>
                  <button type="button" className="prodpick__row tap-feedback" onClick={() => pick(name, null)}>
                    {name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {shown.map((group) => (
          <section key={group.key} className="prodpick__group" aria-label={group.label}>
            <h3 className="prodpick__group-title">
              {group.label}
              {group.detail && <span className="prodpick__detail">{group.detail}</span>}
            </h3>
            <ul className="prodpick__list">
              {group.items.map((name) => (
                <li key={`${group.key}-${name}`}>
                  <button type="button" className="prodpick__row tap-feedback" onClick={() => pick(name, group.key)}>
                    {name}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}

        {q && found === 0 && !loading && <p className="prodpick__note">В списке такого нет</p>}

        {q && !exact && (
          <button type="button" className="prodpick__row prodpick__row--own tap-feedback" onClick={() => pick(query.trim(), null)}>
            Использовать «{query.trim()}»
          </button>
        )}
      </DraggableSheetBody>
    </Popup>
  );
}
