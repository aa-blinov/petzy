import { isAxiosError } from 'axios';
import { Dialog } from 'antd-mobile';
import { medicationsService, type IntakeInput } from '../services/medications.service';

/** The server found the same dose already marked close in time (two people, a second tap). */
export interface DuplicateIntake {
  date: string;
  time: string;
  username: string | null;
  own: boolean;
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
export async function logIntakeAsking(medicationId: string, name: string, input: IntakeInput) {
  try {
    return await medicationsService.logIntake(medicationId, input);
  } catch (err) {
    const existing = duplicateOf(err);
    if (!existing || input.force) throw err;
    const who = existing.own ? 'Вы уже отметили этот приём' : `Этот приём уже отмечен: ${existing.username ?? 'другой человек'}`;
    const sure = await Dialog.confirm({
      title: 'Приём уже отмечен',
      content: `${name}. ${who}${existing.own ? ' в ' : ', '}${existing.time}. Записать ещё один?`,
      confirmText: 'Записать ещё',
      cancelText: 'Не записывать',
    });
    if (!sure) throw new IntakeDeclined();
    return medicationsService.logIntake(medicationId, { ...input, force: true });
  }
}
