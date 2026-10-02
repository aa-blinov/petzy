import type { QueryClient } from '@tanstack/react-query';

/**
 * Everything that shows a logged dose: the courses (intakes_today, stock),
 * the dose widget, and the feed and History, where the intake is a row in
 * the timeline. The widget used to refresh the courses alone, so a dose
 * given from it didn't appear in the feed below until a reload.
 */
export function refreshAfterIntake(queryClient: QueryClient): Promise<unknown> {
  return queryClient.invalidateQueries({
    predicate: (query) =>
      ['medications', 'timeline', 'history-timeline', 'stats', 'pet-summary', 'pets'].includes(
        query.queryKey[0] as string,
      ) ||
      // The dot on the «Лекарства» tab and the pet switcher: a dose marked puts it out.
      (query.queryKey[0] === 'medical-card' && query.queryKey[2] === 'alerts'),
  });
}
