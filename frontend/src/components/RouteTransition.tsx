/**
 * Wraps the route outlet so each page fades+slides in on navigation.
 *
 * - Forward navigation (push) slides in from the right.
 * - Back navigation (pop) slides in from the left, slightly faster —
 *   returning to a previous view should feel quicker than going
 *   somewhere new.
 * - Replace (a redirect, e.g. the sign-out path) just cross-fades:
 *   there is no direction to imply when the user didn't navigate.
 * - Same-route re-renders don't trigger the animation.
 * - Swiping right from the left edge triggers a back navigation
 *   (basic iOS-style edge gesture).
 *
 * The three states map to `.route-transition--forward|back|replace`,
 * backed by the `route-forward` / `route-back` / `route-fade` keyframes
 * in globals.css.
 *
 * The key on the inner div forces a remount on pathname change, which
 * restarts the CSS animation each time.
 */

import { type ReactNode } from 'react';
import { useLocation, useNavigationType } from 'react-router-dom';
import { useSwipeBack } from '../hooks/useSwipeBack';

export function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navType = useNavigationType(); // 'PUSH' | 'POP' | 'REPLACE'
  const direction: 'forward' | 'back' | 'replace' =
    navType === 'POP' ? 'back' : navType === 'REPLACE' ? 'replace' : 'forward';

  useSwipeBack();

  return (
    <div
      key={location.pathname}
      className={`route-transition route-transition--${direction}`}
    >
      {children}
    </div>
  );
}
