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
   * Update the selected pet's id+name in localStorage only — no query
   * cascade. Used by the auto-select path on first mount, where every
   * pet-scoped query for the new id hasn't been fetched yet (it will
   * run on first render of the consumer, keyed by the new id).
   */
  const setSelectedPet = useCallback((pet: Pet | null) => {
    if (pet) {
      setSelectedPetId(pet._id);
      setSelectedPetName(pet.name);
    } else {
      setSelectedPetId(null);
      setSelectedPetName(null);
    }
  }, [setSelectedPetId, setSelectedPetName]);

  /**
   * Switching the selected pet on user action must invalidate every
   * pet-scoped query so the dashboard, history, medications and next-dose
   * widget all refetch for the new pet. Without this, the navbar shows
   * the new pet's name but the rest of the UI keeps the previous pet's
   * data until the queries next go stale (~30 s).
   *
   * The predicate intentionally excludes the `['pets']` key itself — the
   * pet roster doesn't change when we switch which one is "active",
   * so refetching it just causes a render-storm across every `usePet`
   * consumer (Navbar, PetSummaryCard, NextDoseWidget, …) that would
   * otherwise be visible as flicker on the home page.
   */
  const selectPet = useCallback((pet: Pet | null) => {
    setSelectedPet(pet);
    if (!pet) return;
    queryClient.invalidateQueries({
      predicate: (q) =>
        Array.isArray(q.queryKey) &&
        q.queryKey.some(
          (segment) =>
            typeof segment === 'string' &&
            (
              segment === 'medications' ||
              segment === 'history' ||
              segment === 'future-intakes' ||
              segment === 'dashboard' ||
              segment === 'timeline' ||
              segment.startsWith('pet-summary')
            )
        ),
    });
  }, [queryClient, setSelectedPet]);

  // Auto-select first pet if none selected and pets are available.
  // Also recover from a stale selectedPetId — e.g. after a backend
  // restart with a fresh in-memory DB, the previous pet ID no longer
  // exists and the API returns 403 on every dashboard call. Clear it
  // so the auto-select path below takes over.
  //
  // Uses `setSelectedPet` (storage-only) instead of `selectPet` (full
  // cascade invalidation): on first mount there is no cached data for
  // the new pet id yet, so React Query will fetch every pet-scoped
  // query lazily on its first render — no manual invalidation needed,
  // and importantly no render-storm from re-invalidating the pet roster.
  useEffect(() => {
    if (pets.length === 0) return;
    if (selectedPetId && !pets.find(p => p._id === selectedPetId)) {
      setSelectedPet(pets[0]);
    } else if (!selectedPetId) {
      setSelectedPet(pets[0]);
    }
  }, [pets, selectedPetId, setSelectedPet]);

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