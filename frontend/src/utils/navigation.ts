import type { NavigateFunction } from 'react-router-dom';

/** The bottom tab bar's sections: peers, not steps in a hierarchy. */
export const MAIN_TAB_PATHS = ['/', '/medications', '/documents', '/history', '/settings'];

/**
 * Leave a form the same way the user arrived at it — by going back,
 * not by jumping to one hardcoded destination.
 *
 * Every form in the app (pet, medication, document, user, event type,
 * health record) is a step pushed onto whatever list screen opened it.
 * A form that instead hardcodes its own "next" route breaks in two
 * ways:
 *   - a form reachable from more than one screen (health records: the
 *     Dashboard's quick-add AND a History item's edit swipe both lead
 *     here) can only get one of them right — editing a record from the
 *     Dashboard used to always land on History, because the form had
 *     no idea it had been opened from `/` instead.
 *   - even a form with a single entry point leaves its own route
 *     sitting in history once the destination is pushed on top, so the
 *     first tap on the browser/Navbar back button returns to the
 *     now-stale form instead of leaving the list — a second tap was
 *     needed to actually get anywhere.
 *
 * `navigate(-1)` pops the form's own entry and lands exactly back on
 * whichever screen (and scroll position, filter, tab, …) opened it,
 * for every entry point at once, with no route to keep in sync by
 * hand. `fallback` only matters when the form was opened with no prior
 * history in this session (e.g. a deep link) — `history.length` here
 * mirrors the same check Navbar's own back button already uses.
 */
export function goBack(navigate: NavigateFunction, fallback: string): void {
  if (window.history.length > 1) {
    navigate(-1);
  } else {
    navigate(fallback, { replace: true });
  }
}
