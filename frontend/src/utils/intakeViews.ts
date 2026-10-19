import type { QueryClient } from '@tanstack/react-query';

/** The names the views a course and a dose show up in give their queries. None of them starts with 'medications',
 *  so invalidateQueries(['medications']) reaches the courses alone and every other view keeps showing what the
 *  change removed until its own staleTime lapses. */
const VIEWS = ['medications', 'medical-card', 'timeline', 'history-timeline', 'stats', 'pet-summary', 'pets'];

/**
 * Everything that shows a course: the courses themselves, the dose widget, the medical card, and the feed and
 * History, where the course and its doses are rows in the timeline. Saving, finishing, resuming or deleting a
 * course goes through here, so one list of keys serves them all.
 */
export function refreshMedicationViews(queryClient: QueryClient): Promise<unknown> {
  return queryClient.invalidateQueries({ predicate: (query) => VIEWS.includes(query.queryKey[0] as string) });
}

/**
 * Everything that shows a logged dose: the courses (intakes_today, stock),
 * the dose widget, and the feed and History, where the intake is a row in
 * the timeline. The widget used to refresh the courses alone, so a dose
 * given from it didn't appear in the feed below until a reload.
 */
export function refreshAfterIntake(queryClient: QueryClient): Promise<unknown> {
  return queryClient.invalidateQueries({
    predicate: (query) =>
      VIEWS.includes(query.queryKey[0] as string) &&
      // The card holds courses, not doses: of it only the dot on the «Лекарства» tab and the pet switcher moves.
      (query.queryKey[0] !== 'medical-card' || query.queryKey[2] === 'alerts'),
  });
}
