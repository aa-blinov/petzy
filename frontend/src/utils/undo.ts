/**
 * «Отменить» after an action already taken by mistake (a dose marked with a
 * stray tap): a bar at the bottom for a few seconds instead of a
 * confirmation before every action. The bar is utils/snackbar.ts's; a newer
 * message replaces the one on screen.
 *
 * For an action that can't be reversed after the fact (deleting a record),
 * see utils/deferredDelete.ts: it waits, and only then does it.
 */

import { showToast } from './toast';
import { showSnackbar } from './snackbar';

export interface UndoRequest {
  message: string;
  /** Reverts the action; rejects to show «Не удалось отменить». */
  onUndo: () => Promise<void>;
}

export function showUndo(request: UndoRequest): void {
  showSnackbar({
    message: request.message,
    tone: 'success',
    action: {
      label: 'Отменить',
      run: async () => {
        try {
          await request.onUndo();
        } catch {
          showToast.failure('Не удалось отменить');
          return;
        }
        showToast.success('Отменено');
      },
    },
  });
}
