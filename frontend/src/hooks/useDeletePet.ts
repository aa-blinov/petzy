import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { deleteWithUndo } from '../utils/deferredDelete';
import { expectPetGone, usePet } from './usePet';

/**
 * Takes a pet off the list and keeps the selection sensible: if it was
 * the selected one, the pet in its place is selected next (or none, if it
 * was the last). Rejects on failure, after telling the user why.
 */
function useRemoveFromList(remove: (petId: string) => Promise<void>, done: string, failed: string) {
  const queryClient = useQueryClient();
  const { pets, selectPet, getSelectedPet } = usePet();

  return async (pet: Pet) => {
    try {
      const wasSelected = getSelectedPet?._id === pet._id;
      const index = pets.findIndex((p) => p._id === pet._id);

      expectPetGone(pet._id);
      await remove(pet._id);

      const updated = await petsService.getPets();
      queryClient.setQueryData(['pets'], updated);
      if (updated.length === 0) selectPet(null);
      else if (wasSelected) selectPet(updated[Math.min(index, updated.length - 1)]);

      showToast.success(done);
    } catch (error) {
      showToast.failure(getApiErrorMessage(error, failed));
      throw error;
    }
  };
}

/** The owner deletes a pet. Shared by the pets list's swipe and the edit form's button.
 *  The pet leaves the lists at once and «Отменить» is on offer; the server is asked when that time is up. */
export function useDeletePet() {
  const queryClient = useQueryClient();
  const { selectPet, getSelectedPet } = usePet();

  return async (pet: Pet) => {
    const wasSelected = getSelectedPet?._id === pet._id;
    expectPetGone(pet._id);
    deleteWithUndo({
      id: pet._id,
      path: `/pets/${pet._id}`,
      message: `«${pet.name}» удалён`,
      failure: `Не удалось удалить «${pet.name}», питомец на месте`,
      onUndo: () => {
        if (wasSelected) selectPet(pet);
      },
      onDeleted: async () => {
        queryClient.setQueryData(['pets'], await petsService.getPets());
      },
    });
  };
}

/** Someone a pet was shared with stops seeing it; the owner keeps everything. */
export function useLeavePet() {
  return useRemoveFromList((id) => petsService.leavePet(id), 'Вы больше не видите этого питомца', 'Не удалось выйти');
}
