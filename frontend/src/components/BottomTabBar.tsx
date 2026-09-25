import { NavLink, useLocation } from 'react-router-dom';
import { BookOpen, Pill, FileText, Clock, SlidersHorizontal } from 'lucide-react';

const tabs = [
  { to: '/', title: 'Лента', Icon: BookOpen },
  { to: '/medications', title: 'Лекарства', Icon: Pill },
  { to: '/documents', title: 'Документы', Icon: FileText },
  { to: '/history', title: 'История', Icon: Clock },
  { to: '/settings', title: 'Настройки', Icon: SlidersHorizontal },
];

/**
 * Real links in a <nav>. antd-mobile's TabBar rendered each tab as a
 * bare div with an onClick: unreachable by Tab, silent to a screen
 * reader, and the current tab was marked by colour alone. NavLink gives
 * Enter/Space, a link role and aria-current="page" for free.
 */
export function BottomTabBar() {
  const { pathname } = useLocation();

  // Login and onboarding own the whole viewport
  if (pathname === '/login' || pathname === '/welcome') {
    return null;
  }

  return (
    <nav className="bottom-tab-bar-container" aria-label="Разделы">
      <ul className="app-tab-bar">
        {tabs.map(({ to, title, Icon }) => (
          <li key={to}>
            <NavLink
              to={to}
              // Exact match, as before: /pets is reached from Settings but
              // isn't the Settings tab itself.
              end
              className={({ isActive }) => `app-tab-bar__item${isActive ? ' app-tab-bar__item--active' : ''}`}
            >
              <span className="app-tab-bar__icon" aria-hidden>
                <Icon size={22} strokeWidth={1.8} />
              </span>
              <span className="app-tab-bar__title">{title}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
