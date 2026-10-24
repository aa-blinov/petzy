import { useQueryClient } from '@tanstack/react-query';

/** What a document's link to its records changes on the screens: the lists of documents and the card read the records. */
export function useRefreshAfterLink(petId: string | null | undefined) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ['documents', petId] }),
      queryClient.invalidateQueries({ queryKey: ['document'] }),
      queryClient.invalidateQueries({ queryKey: ['medical-card'] }),
      queryClient.invalidateQueries({ queryKey: ['medical-records'] }),
    ]);
}
