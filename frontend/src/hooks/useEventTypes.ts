import { useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from './useSession';
import { eventTypesService, type EventType } from '../services/eventTypes.service';

/** The event-type registry rarely changes — one fetch per session is
 *  enough, refreshed explicitly (see useInvalidateEventTypes) whenever a
 *  type is created/edited/deleted.
 *
 *  `error` is handed back on purpose: without it a failed request looked
 *  like an empty registry, and a page that asks for types (the factory,
 *  a new record) said there were none instead of that it couldn't read
 *  them. */
export function useEventTypes() {
  const { isAuthenticated, isLoginPage } = useSession();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['event-types'],
    queryFn: () => eventTypesService.list(),
    enabled: !isLoginPage && isAuthenticated !== false,
    staleTime: 5 * 60 * 1000,
  });

  const eventTypes = useMemo(() => data ?? [], [data]);
  const eventTypesByKey = useMemo(
    () => Object.fromEntries(eventTypes.map((t) => [t.key, t])) as Record<string, EventType>,
    [eventTypes]
  );

  return { eventTypes, eventTypesByKey, isLoading, error, refetch };
}

export function useInvalidateEventTypes() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ['event-types'] });
}
