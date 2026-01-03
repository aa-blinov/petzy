import { useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocalStorage } from './useLocalStorage';
import { petsService, type Pet } from '../services/pets.service';

export function usePet() {
  const [selectedPetId, setSelectedPetId] = useLocalStorage<string | null>('selectedPetId', null);
  const [selectedPetName, setSelectedPetName] = useLocalStorage<string | null>('selectedPetName', null);

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

  const selectPet = (pet: Pet | null) => {
    if (pet) {
      setSelectedPetId(pet._id);
      setSelectedPetName(pet.name);
    } else {
      setSelectedPetId(null);
      setSelectedPetName(null);
    }
  };

  // Auto-select first pet if none selected and pets are available
  useEffect(() => {
    if (pets.length > 0 && !selectedPetId) {
      selectPet(pets[0]);
    }
  }, [pets, selectedPetId]);

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

