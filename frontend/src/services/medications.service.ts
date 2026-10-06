import api from './api';
import { formatDate } from '../utils/dateUtils';
import { deviceTimeZone } from '../utils/timezone';

export interface MedicationSchedule {
    days: number[]; // 0-6
    times: string[]; // HH:mm
}

export interface Medication {
    _id: string;
    pet_id: string;
    name: string;
    type: string;
    form_factor?: 'tablet' | 'liquid' | 'injection' | 'other';
    strength?: string;
    dose_unit?: string;
    default_dose?: number;
    dosage?: string; // legacy
    unit?: string; // legacy
    schedule: MedicationSchedule;
    /** «По необходимости»: a dose is marked when it is given, not at a time.
     *  Absent on a course stored before the flag, when the mode was the empty
     *  schedule; the backend resolves those and always sends the flag. */
    as_needed?: boolean;
    inventory_enabled: boolean;
    inventory_total?: number;
    inventory_current?: number;
    /** Legacy: warn at this amount. New courses warn by days (below). */
    inventory_warning_threshold?: number;
    /** Warn when the stock covers this many days or fewer (default 3). */
    inventory_warning_days?: number;
    /** How many days the stock lasts on this schedule; null without one. */
    inventory_days_left?: number | null;
    inventory_low?: boolean;
    is_active: boolean;
    comment?: string;
    /** YYYY-MM-DD; absent for courses made before dates existed. */
    started_on?: string | null;
    ended_on?: string | null;
    /** От чего или для чего назначен. */
    purpose?: string;
    prescribed_by?: string;
    /** active (идёт), planned (ещё не началась), ended (закончена). */
    course_status?: 'active' | 'planned' | 'ended';
    last_taken_at?: string;
    /** Who marked the last dose. */
    last_taken_by?: string | null;
    /** The zone of the clock last_taken_at was marked on. */
    last_taken_tz?: string | null;
    intakes_today?: number;
    /** Today's schedule has doses (day of the week and course). */
    scheduled_today?: boolean;
    /** Today's scheduled times nothing has closed yet, in order. */
    open_slots_today?: string[];
    username?: string;
}

export interface MedicationCreate {
    pet_id: string;
    name: string;
    type: string;
    form_factor?: string;
    strength?: string;
    dose_unit?: string;
    default_dose?: number;
    dosage?: string;
    unit?: string;
    schedule: MedicationSchedule;
    /** The mode is chosen, not derived: a course «по необходимости» keeps its
     *  days and times and is not reminded about. */
    as_needed?: boolean;
    inventory_enabled?: boolean;
    inventory_total?: number;
    inventory_current?: number;
    inventory_warning_threshold?: number;
    inventory_warning_days?: number;
    is_active?: boolean;
    comment?: string;
    /** A date or text is cleared with an empty string. */
    started_on?: string;
    ended_on?: string;
    purpose?: string;
    prescribed_by?: string;
}

/** Examples to start a form from: the name, the form and the strength of the box. The dose is the vet's to set, so none is put in. */
export const COMMON_MEDICATIONS = [
    { name: 'Синулокс 50мг', type: 'Таблетка', form_factor: 'tablet', strength: '50 мг', dose_unit: 'таб' },
    { name: 'Синулокс 250мг', type: 'Таблетка', form_factor: 'tablet', strength: '250 мг', dose_unit: 'таб' },
    { name: 'Габапентин', type: 'Капсула', form_factor: 'tablet', strength: '300 мг', dose_unit: 'капс' },
    { name: 'Мелоксидил', type: 'Суспензия', form_factor: 'liquid', strength: '0,5 мг/мл', dose_unit: 'мл' },
    { name: 'Преднизолон', type: 'Таблетка', form_factor: 'tablet', strength: '5 мг', dose_unit: 'таб' },
    { name: 'Онсиор', type: 'Таблетка', form_factor: 'tablet', strength: '6 мг', dose_unit: 'таб' },
    { name: 'Доксициклин', type: 'Таблетка', form_factor: 'tablet', strength: '100 мг', dose_unit: 'таб' },
];

export interface MedicationIntake {
    _id: string;
    medication_id: string;
    pet_id: string;
    date_time: string;
    dose_taken: number;
    username: string;
    comment?: string;
    /** «Пропустить»: the slot is handled, nothing was given. */
    skipped?: boolean;
}

/** What is sent to log a dose. ``slot_*``: the scheduled dose it is for, so that one is closed, not the earliest. */
export interface IntakeInput {
    date: string;
    time: string;
    dose_taken?: number;
    comment?: string;
    skipped?: boolean;
    slot_date?: string;
    slot_time?: string;
    /** Record it although the same dose is already marked close in time. */
    force?: boolean;
}

export interface UpcomingDose {
    medication_id: string;
    name: string;
    type: string;
    time: string;
    date: string;
    is_overdue: boolean;
    inventory_warning: boolean;
    /** Last evening's dose that nobody marked, still offered for a few hours after midnight. */
    carried_over?: boolean;
}

export const medicationsService = {
    async getList(petId: string, clientDate?: string): Promise<Medication[]> {
        const response = await api.get<{ medications: Medication[] }>('/medications', {
            params: {
                pet_id: petId,
                client_date: clientDate
            }
        });
        return response.data.medications;
    },

    async create(data: MedicationCreate): Promise<string> {
        const response = await api.post<{ id: string }>('/medications', data);
        return response.data.id;
    },

    async getById(id: string): Promise<Medication> {
        const response = await api.get<{ medication: Medication }>(`/medications/${id}`);
        return response.data.medication;
    },

    async update(id: string, data: Partial<MedicationCreate>): Promise<void> {
        await api.put(`/medications/${id}`, data);
    },

    async delete(id: string): Promise<void> {
        await api.delete(`/medications/${id}`);
    },

    /** Always records the dose; ``ran_out`` says the stock is now empty,
     *  ``id`` is the intake's, for «Отменить». */
    async logIntake(id: string, data: IntakeInput): Promise<{ id: string; ran_out: boolean }> {
        // Fifteen seconds, not thirty: a mark with no answer by then is kept on the phone and sent later.
        const response = await api.post<{ id: string; ran_out?: boolean }>(`/medications/${id}/log`, { ...data, tz: deviceTimeZone() }, { timeout: 15_000 });
        return { id: response.data.id, ran_out: !!response.data.ran_out };
    },

    /** Move a logged dose to when it was really given. */
    async updateIntakeTime(intakeId: string, when: { date: string; time: string }): Promise<void> {
        await api.put(`/medications/intakes/${intakeId}`, { ...when, tz: deviceTimeZone() });
    },

    /** Delete a logged dose (its stock comes back). Not /events/: intakes
     *  live in their own collection. */
    async deleteIntake(intakeId: string): Promise<void> {
        await api.delete(`/medications/intakes/${intakeId}`);
    },

    /** Add a bought pack to the stock. Returns the new stock. */
    async restock(id: string, amount: number): Promise<number> {
        const response = await api.post<{ inventory_current: number }>(`/medications/${id}/restock`, { amount });
        return response.data.inventory_current;
    },

    async getUpcoming(petId: string, clientDatetime?: string): Promise<UpcomingDose[]> {
        const response = await api.get<{ doses: UpcomingDose[] }>('/medications/upcoming', {
            params: {
                pet_id: petId,
                client_datetime: clientDatetime
            }
        });
        return response.data.doses;
    }
};

/** The medications list query, shared by the page and the tab prefetch
 *  (App.tsx) so both fill the same cache entry. */
export function medicationsListQuery(petId: string) {
    return {
        queryKey: ['medications', petId] as const,
        // Local date, not the UTC one toISOString() yields: the backend
        // uses this as the start of "today" when deciding which doses are
        // already taken, so a UTC date put the window on the wrong day
        // near midnight.
        queryFn: () => medicationsService.getList(petId, formatDate(new Date())),
        // Another person may mark a dose: the list is looked at again when the app comes back to the front and every half minute.
        refetchOnWindowFocus: true,
        refetchInterval: 30000,
        staleTime: 5000,
    };
}
