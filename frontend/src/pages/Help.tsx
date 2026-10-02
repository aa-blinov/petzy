import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import { HELP_FAQ, HELP_SCREENS, type HelpBlock, type HelpEntry } from '../content/help';
import './Help.css';

function Block({ block }: { block: HelpBlock }) {
  if (typeof block === 'string') return <p>{block}</p>;
  return (
    <ul>
      {block.list.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function Section({ title, entries, searching }: { title: string; entries: HelpEntry[]; searching: boolean }) {
  if (entries.length === 0) return null;
  return (
    <section className="help-section">
      <h2 className="section-header">{title}</h2>
      <div className="card-soft help-card">
        {entries.map((entry) => (
          // <details>: a native disclosure, keyboard and screen reader
          // ready, and openable from the URL hash (below).
          // While a search is on, what it found is open: the answer is the point, not one more tap to reach it.
          <details key={`${entry.id}-${searching ? 'found' : 'all'}`} id={entry.id} className="help-item" open={searching || undefined}>
            <summary>
              <span>{entry.title}</span>
              <ChevronDown size={18} strokeWidth={2.2} aria-hidden className="help-item__chevron" />
            </summary>
            <div className="help-item__body">
              {entry.body.map((block, i) => (
                <Block key={i} block={block} />
              ))}
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

/** Настройки → «Справка»: common questions, then how each screen works. */
export function Help() {
  const { hash } = useLocation();
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase().replace(/ё/g, 'е');
  const matches = (entry: HelpEntry) => !needle || needle.split(/\s+/).every((word) => textOf(entry).includes(word));
  const faq = HELP_FAQ.filter(matches);
  const screens = HELP_SCREENS.filter(matches);

  // /help#documents opens that section and brings it into view.
  useEffect(() => {
    if (!hash) return;
    const target = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
      target.scrollIntoView({ block: 'start' });
    }
  }, [hash]);

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h1 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            Справка
          </h1>
          <p style={{ margin: 'var(--spacing-sm) 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            Ответы на частые вопросы и как устроен каждый экран
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
          {needle && faq.length + screens.length === 0 && (
            <p className="help-empty" role="status">
              Ничего не нашлось. Попробуйте другое слово, например «напоминание» или «врач»
            </p>
          )}
          <Section title="Частые вопросы" entries={faq} searching={!!needle} />
          <Section title="Экраны" entries={screens} searching={!!needle} />
        </div>
      </div>
    </div>
  );
}
