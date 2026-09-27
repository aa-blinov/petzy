import { useQuery } from '@tanstack/react-query';
import { petsService } from '../services/pets.service';

export const PET_INVITES_QUERY_KEY = ['pet-invites'] as const;

/** The invitations waiting for an answer; empty for most people. */
export function usePetInvites() {
  return useQuery({
    queryKey: PET_INVITES_QUERY_KEY,
    queryFn: () => petsService.getInvites(),
    staleTime: 30_000,
  });
}
