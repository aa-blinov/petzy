import { isAxiosError } from 'axios';
import { Dialog } from 'antd-mobile';
import { medicationsService, type IntakeInput } from '../services/medications.service';
import { enqueueIntake, isOffline } from './offlineIntakes';

/** The server found the same dose already marked: the slot it was for (the dose widget names
 *  it) or a dose given close in time (two taps by one finger). */
export interface DuplicateIntake {
  date: string;
  time: string;
  username: string | null;
  own: boolean;
  /** True when the clash is about a scheduled slot, false when about the time alone. */
  slot?: boolean;
}

/** The person was asked and said no: nothing was recorded, and nothing needs saying. */
export class IntakeDeclined extends Error {
  constructor() {
    super('intake declined');
  }
}

export function duplicateOf(err: unknown): DuplicateIntake | null {
  if (!isAxiosError(err) || err.response?.status !== 409) return null;
  const body = err.response.data as { code?: string; existing?: DuplicateIntake } | undefined;
  return body?.code === 'duplicate_intake' && body.existing ? body.existing : null;
}

/** Logs a dose; when it is the same one already marked, says who marked it and when, and records another only if asked to. */
export async function logIntakeAsking(medicationId: string, name: string, input: IntakeInput): Promise<{ id: string; ran_out: boolean; queued?: boolean }> {
  try {
    return await medicationsService.logIntake(medicationId, input);
  } catch (err) {
    if (isOffline(err)) {
      enqueueIntake(medicationId, name, input);
      return { id: '', ran_out: false, queued: true };
    }
    const existing = duplicateOf(err);
    if (!existing || input.force) throw err;
    // A clash about a slot is about that time of the schedule, however long ago it was given;
    // a clash about the time alone is a dose given minutes apart from this one. Whose it was is
    // said with «вами» or a name, never with the person's gender in the verb.
    const who = existing.own ? ' вами' : `: ${existing.username ?? 'другой человек'}`;
    const sure = await Dialog.confirm({
      title: existing.slot ? 'Это время уже отмечено' : 'Приём уже отмечен',
      content: existing.slot
        ? `${name}: приём на ${existing.time} уже отмечен${who}. Записать ещё один?`
        : `${name}. Приём уже отмечен${who} в ${existing.time}. Записать ещё один?`,
      confirmText: 'Записать ещё',
      cancelText: 'Не записывать',
    });
    if (!sure) throw new IntakeDeclined();
    return medicationsService.logIntake(medicationId, { ...input, force: true });
  }
}
