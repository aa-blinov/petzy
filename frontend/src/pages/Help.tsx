import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { HELP_FAQ, HELP_SCREENS, type HelpEntry } from '../content/help';
import './Help.css';

function Section({ title, entries, searching, words, opened, onToggle, wanted }: {
  title: string;
  entries: HelpEntry[];
  searching: boolean;
  words: string[];
  opened: Record<string, boolean>;
  onToggle: (id: string, open: boolean) => void;
  /** The entry a link (/help#id) named: open on arrival. */
  wanted: string;
}) {
  if (entries.length === 0) return null;
  return (
    <section className="help-section">
      <h2 className="section-header">{title}</h2>
      <div className="card-soft help-card">
        {entries.map((entry) => (
          // <details>: a native disclosure, keyboard and screen reader
          // ready, and openable from the URL hash (below).
          // While a search is on, what it found is open: the answer is the point, not one more tap to reach it.
          // The key is the entry itself, never the state of the search: a key
          // that changed with the search remounted every entry, so clearing
          // the line closed whatever the person had opened with their hands.
          <details
            key={entry.id}
            id={entry.id}
            className="help-item"
            open={searching ? true : !!opened[entry.id] || entry.id === wanted}
            onToggle={(event) => onToggle(entry.id, event.currentTarget.open)}
          >
            <summary>
              <span><Highlighted text={entry.title} words={words} /></span>
              <ChevronDown size={18} strokeWidth={2.2} aria-hidden className="help-item__chevron" />
            </summary>
            <div className="help-item__body">
              {entry.body.map((block, i) =>
                typeof block === 'string' ? (
                  <p key={i}><Highlighted text={block} words={words} /></p>
                ) : (
                  <ul key={i}>
                    {block.list.map((item, j) => (
                      <li key={j}><Highlighted text={item} words={words} /></li>
                    ))}
                  </ul>
                ),
              )}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

/** The text of an entry the search looks through: the question and every line of the answer. */
function textOf(entry: HelpEntry): string {
  const body = entry.body.map((block) => (typeof block === 'string' ? block : block.list.join(' '))).join(' ');
  return `${entry.title} ${body}`.toLowerCase().replace(/ё/g, 'е');
}

/** A line of the answer with the words that were searched for marked, so a
 *  match is visible in the text and not only in the list of results. */
function Highlighted({ text, words }: { text: string; words: string[] }) {
  if (words.length === 0) return <>{text}</>;
  const escaped = words.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return (
    <>
      {parts.map((part, i) =>
        words.includes(part.toLowerCase().replace(/ё/g, 'е')) ? (
          <mark
            key={i}
            style={{
              backgroundColor: 'var(--app-accent-soft)',
              color: 'inherit',
              borderRadius: 2,
              padding: '0 2px',
            }}
          >
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

/** Настройки → «Справка»: common questions, then how each screen works. */
export function Help() {
  const { hash } = useLocation();
  const [query, setQuery] = useState('');
  // Which entries the person opened by hand, so a search and its clearing
  // leave them as they were.
  const [opened, setOpened] = useState<Record<string, boolean>>({});
  const needle = query.trim().toLowerCase().replace(/ё/g, 'е');
  // Any of the words is enough: requiring all of them found a question only
  // when it happened to repeat the whole phrase.
  const words = needle.split(/\s+/).filter(Boolean);
  const matches = (entry: HelpEntry) => !needle || words.some((word) => textOf(entry).includes(word));
  // A link to one entry (/help#documents) out of a search: the entry the link
  // names is shown whatever the search line says, or the link leads nowhere
  // without a word about it.
  const wanted = hash ? decodeURIComponent(hash.slice(1)) : '';
  const keep = (entry: HelpEntry) => matches(entry) || entry.id === wanted;
  const faq = HELP_FAQ.filter(keep);
  const screens = HELP_SCREENS.filter(keep);
  const found = faq.length + screens.length;

  // /help#documents opens that section and brings it into view. Which one is
  // open comes from `wanted` and `opened`, so the effect only brings it into
  // view and doesn't have to write state of its own.
  useEffect(() => {
    if (!wanted) return;
    const target = document.getElementById(wanted);
    if (target instanceof HTMLDetailsElement) target.scrollIntoView({ block: 'start' });
  }, [wanted]);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 className="display-headline" style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 500, margin: 0 }}>
            Справка
          </h1>
          <p style={{ margin: 'var(--spacing-xs) 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Ответы на частые вопросы и как устроены основные экраны
          </p>
        </div>
        <div className="safe-area-padding">
          <input
            type="search"
            className="help-search"
            placeholder="Найти в справке"
            aria-label="Поиск по справке"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {/* How much the search found, so an empty-looking list isn't read as
              a broken screen. */}
          {needle && found > 0 && (
            <p className="help-empty" role="status" style={{ margin: 'var(--spacing-sm) 0 0', fontSize: 'var(--text-sm)' }}>
              {`Найдено: ${found}`}
            </p>
          )}
          {needle && found === 0 && (
            <p className="help-empty" role="status">
              Ничего не нашлось. Попробуйте другое слово, например «напоминание» или «врач»
            </p>
          )}
          {!needle && wanted && !HELP_FAQ.some((e) => e.id === wanted) && !HELP_SCREENS.some((e) => e.id === wanted) && (
            <p className="help-empty" role="status">
              Такого раздела в справке нет
            </p>
          )}
          <Section
            title="Частые вопросы"
            entries={faq}
            searching={!!needle}
            words={words}
            opened={opened}
            onToggle={(id, open) => setOpened((current) => ({ ...current, [id]: open }))}
            wanted={wanted}
          />
          <Section
            title="Экраны"
            entries={screens}
            searching={!!needle}
            words={words}
            opened={opened}
            onToggle={(id, open) => setOpened((current) => ({ ...current, [id]: open }))}
            wanted={wanted}
          />
        </div>
      </div>
    </div>
  );
}
