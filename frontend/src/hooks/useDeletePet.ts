import { useQueryClient } from '@tanstack/react-query';
import { petsService, type Pet } from '../services/pets.service';
import { getApiErrorMessage } from '../utils/apiError';
import { showToast } from '../utils/toast';
import { showSnackbar } from '../utils/snackbar';
import { deleteWithUndo } from '../utils/deferredDelete';
import { expectPetGone, usePet } from './usePet';

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

/** Someone a pet was shared with stops seeing it. The owner keeps everything, and the question asked before
 *  it is not the owner's deletion question. The request still goes last, so that this action has the same
 *  «Отменить» the owner's has: one swipe used to take a pet away for good, with no way back but a new
 *  invite from the owner, and the same question the owner's deletion asks. Nothing is sent while the bar
 *  is up, so «Отменить» costs nothing.
 *  (deleteWithUndo could not be reused: leaving is a POST, and utils/deferredDelete.ts sends a DELETE.) */
export function useLeavePet() {
  const queryClient = useQueryClient();
  const { pets, selectPet, getSelectedPet } = usePet();

  return async (pet: Pet) => {
    const wasSelected = getSelectedPet?._id === pet._id;
    const index = pets.findIndex((p) => p._id === pet._id);

    // Gone from the lists right away, before the server has been asked.
    expectPetGone(pet._id);
    queryClient.setQueryData(['pets'], pets.filter((p) => p._id !== pet._id));
    if (wasSelected) selectPet(null);

    showSnackbar({
      message: `Вы больше не видите «${pet.name}»`,
      tone: 'success',
      action: {
        label: 'Отменить',
        run: () => {
          showToast.success('Вы снова видите этого питомца');
        },
      },
      onDismiss: async (reason) => {
        // A bar another message took over is not a decision either: the access is
        // only given up when the offer is read and closed. Same rule as the queue
        // of deletions in utils/deferredDelete.ts, or leaving shared access would
        // go through silently whenever another message comes along.
        if (reason === 'replaced') return;
        if (reason === 'action') {
          // The list is put back as it was: nothing was ever sent.
          queryClient.setQueryData(['pets'], pets);
          if (wasSelected) selectPet(pets[Math.min(index, pets.length - 1)] ?? null);
          return;
        }
        try {
          await petsService.leavePet(pet._id);
          queryClient.setQueryData(['pets'], await petsService.getPets());
        } catch (error) {
          showToast.failure(getApiErrorMessage(error, 'Не удалось выйти из доступа, питомец на месте'));
          queryClient.setQueryData(['pets'], await petsService.getPets());
        }
      },
    });
  };
}
