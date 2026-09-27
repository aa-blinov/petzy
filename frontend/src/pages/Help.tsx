import { useEffect } from 'react';
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

function Section({ title, entries }: { title: string; entries: HelpEntry[] }) {
  return (
    <section className="help-section">
      <h2 className="section-header">{title}</h2>
      <div className="card-soft help-card">
        {entries.map((entry) => (
          // <details>: a native disclosure, keyboard and screen reader
          // ready, and openable from the URL hash (below).
          <details key={entry.id} id={entry.id} className="help-item">
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

/** Настройки → «Справка»: common questions, then how each screen works. */
export function Help() {
  const { hash } = useLocation();

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
          <Section title="Частые вопросы" entries={HELP_FAQ} />
          <Section title="Экраны" entries={HELP_SCREENS} />
        </div>
      </div>
    </div>
  );
}
