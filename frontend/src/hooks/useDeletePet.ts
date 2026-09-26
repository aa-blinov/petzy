import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { usePet } from './usePet';

/**
 * Deletes a pet and keeps the selection sensible: if it was the selected
 * one, the pet in its place is selected next (or none, if it was the
 * last). Shared by the pets list's swipe and the edit form's button.
 * Rejects on failure, after telling the user why.
 */
export function useDeletePet() {
  const queryClient = useQueryClient();
  const { pets, selectPet, getSelectedPet } = usePet();

  return async (pet: Pet) => {
    try {
      const wasSelected = getSelectedPet?._id === pet._id;
      const index = pets.findIndex((p) => p._id === pet._id);

      await petsService.deletePet(pet._id);

      const updated = await petsService.getPets();
      queryClient.setQueryData(['pets'], updated);
      if (updated.length === 0) selectPet(null);
      else if (wasSelected) selectPet(updated[Math.min(index, updated.length - 1)]);

      showToast.success('Питомец удалён');
    } catch (error) {
      showToast.failure(getApiErrorMessage(error, 'Не удалось удалить'));
      throw error;
    }
  };
}
