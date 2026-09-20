import { useMemo, useEffect, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalStorage } from './useLocalStorage';
import { petsService, type Pet } from '../services/pets.service';

export function usePet() {
  const [selectedPetId, setSelectedPetId] = useLocalStorage<string | null>('selectedPetId', null);
  const [selectedPetName, setSelectedPetName] = useLocalStorage<string | null>('selectedPetName', null);
  const queryClient = useQueryClient();

  // Use React Query to cache pets data - shared across all components
  // React Query automatically deduplicates requests with the same key
  // Use refetchOnMount: false to prevent refetching if data is already in cache
  const { data: pets = [], isLoading } = useQuery({
    queryKey: ['pets'],
    queryFn: () => petsService.getPets(),
    staleTime: 30 * 1000, // Consider data fresh for 30 seconds (matches App.tsx default)
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
    refetchOnMount: false, // Don't refetch if data is already in cache
    refetchOnWindowFocus: false, // Already set in App.tsx, but explicit here
  });

  /**
   * Switching the selected pet must invalidate every pet-scoped query
   * so the dashboard, history, medications and next-dose widget all
   * refetch for the new pet. Without this, the navbar shows the new
   * pet's name but the rest of the UI keeps the previous pet's data
   * until the queries next go stale (~30 s). One switch → full
   * cascade refetch keeps the UI in lockstep with the selection.
   */
  const selectPet = useCallback((pet: Pet | null) => {
    if (pet) {
      setSelectedPetId(pet._id);
      setSelectedPetName(pet.name);
    } else {
      setSelectedPetId(null);
      setSelectedPetName(null);
    }
    // Drop every query that takes pet_id as part of its key, so the
    // next render fetches fresh data for the new selection.
    queryClient.invalidateQueries({
      predicate: (q) =>
        Array.isArray(q.queryKey) &&
        q.queryKey.some(
          (segment) =>
            (typeof segment === 'string' && (segment === 'pets' || segment === 'medications' || segment === 'history' || segment === 'future-intakes' || segment === 'dashboard' || segment.startsWith('pet-'))) ||
            (Array.isArray(segment) && segment.length > 0 && typeof segment[0] === 'string' && segment[0] === 'pets')
        ),
    });
  }, [queryClient, setSelectedPetId, setSelectedPetName]);

  // Auto-select first pet if none selected and pets are available.
  // Also recover from a stale selectedPetId — e.g. after a backend
  // restart with a fresh in-memory DB, the previous pet ID no longer
  // exists and the API returns 403 on every dashboard call. Clear it
  // so the auto-select path below takes over.
  useEffect(() => {
    if (pets.length === 0) return;
    if (selectedPetId && !pets.find(p => p._id === selectedPetId)) {
      selectPet(pets[0]);
    } else if (!selectedPetId) {
      selectPet(pets[0]);
    }
  }, [pets, selectedPetId, selectPet]);

  const getSelectedPet = useMemo((): Pet | null => {
    if (!selectedPetId) return null;
    return pets.find(p => p._id === selectedPetId) || null;
  }, [pets, selectedPetId]);

  return {
    selectedPetId,
    selectedPetName,
    pets,
    isLoading,
    selectPet,
    getSelectedPet
  };
}

