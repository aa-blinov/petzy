import { Link, useLocation } from 'react-router-dom';
import { BookOpen, FileHeart, FileText, Pill, SlidersHorizontal } from 'lucide-react';
import { usePet } from '../hooks/usePet';
import { isPublicPage } from '../utils/publicPages';
import { scrollToTop } from '../utils/scroll';

/** The medical card is a page of one pet: its tab leads to the card of the pet chosen in the top bar, and stays
    the current tab on the card's own screens (the profile, a record, «К приёму»). */
const MEDICAL_PATH = /^\/pets\/[^/]+\/(medical-|visit-prep)/;

const tabs = [
  { key: 'feed', to: '/', title: 'Лента', Icon: BookOpen },
  { key: 'medications', to: '/medications', title: 'Лекарства', Icon: Pill },
  { key: 'medical', to: '', title: 'Медкарта', Icon: FileHeart },
  { key: 'documents', to: '/documents', title: 'Документы', Icon: FileText },
  { key: 'settings', to: '/settings', title: 'Настройки', Icon: SlidersHorizontal },
];

/**
 * Real links in a <nav>. antd-mobile's TabBar rendered each tab as a
 * bare div with an onClick: unreachable by Tab, silent to a screen
 * reader, and the current tab was marked by colour alone. A link gives
 * Enter/Space and a link role; aria-current="page" is set on the current tab.
 */
export function BottomTabBar() {
  const { pathname } = useLocation();
  const { selectedPetId } = usePet();

  // Login and onboarding own the whole viewport
  if (isPublicPage(pathname) || pathname === '/welcome') {
    return null;
  }

  return (
    <nav className="bottom-tab-bar-container" aria-label="Разделы">
      <ul className="app-tab-bar">
        {tabs.map(({ key, to: fixed, title, Icon }) => {
          // No pet chosen yet: the card has nobody to open, the list of pets is where one is added.
          const to = key === 'medical' ? (selectedPetId ? `/pets/${selectedPetId}/medical-card` : '/pets') : fixed;
          // The current tab: the exact page, as before (/pets is reached from Settings but is not the Settings tab); the
          // medical card is the tab for all of its own screens.
          const current = key === 'medical' ? MEDICAL_PATH.test(pathname) : pathname === fixed;
          return (
            <li key={key}>
              <Link
                to={to}
                aria-current={current ? 'page' : undefined}
                // The tab you are on: nothing to open, so scroll it to the top (as a native tab bar does) instead of
                // pushing the same page.
                onClick={(event) => {
                  if (pathname === to) {
                    event.preventDefault();
                    scrollToTop();
                  }
                }}
                className={`app-tab-bar__item${current ? ' app-tab-bar__item--active' : ''}`}
              >
                <span className="app-tab-bar__icon" aria-hidden>
                  <Icon size={22} strokeWidth={1.8} />
                </span>
                <span className="app-tab-bar__title">{title}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
