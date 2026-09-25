/**
 * Wraps the route outlet so each page fades in on navigation.
 *
 * One transition for every screen change: tabs, forms, nested screens,
 * back, redirects. The fade itself lives on `.route-transition` in
 * globals.css (the same short fade the onboarding steps use).
 *
 * - Same-route re-renders don't trigger the animation.
 * - Swiping right from the left edge triggers a back navigation
 *   (basic iOS-style edge gesture).
 *
 * The key on the inner div forces a remount on pathname change, which
 * restarts the CSS animation each time.
 */

import { type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useSwipeBack } from '../hooks/useSwipeBack';

export function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();

  useSwipeBack();

  return (
    <div key={location.pathname} className="route-transition">
      {children}
    </div>
  );
}
