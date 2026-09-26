import api from './api';
import { formatDate } from '../utils/dateUtils';

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
    last_taken_at?: string;
    intakes_today?: number;
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
    inventory_enabled?: boolean;
    inventory_total?: number;
    inventory_current?: number;
    inventory_warning_threshold?: number;
    inventory_warning_days?: number;
    is_active?: boolean;
    comment?: string;
}

export const COMMON_MEDICATIONS = [
    { name: 'Синулокс 50мг', type: 'Таблетка', form_factor: 'tablet', strength: '50 мг', dose_unit: 'таб', default_dose: 1 },
    { name: 'Синулокс 250мг', type: 'Таблетка', form_factor: 'tablet', strength: '250 мг', dose_unit: 'таб', default_dose: 0.5 },
    { name: 'Габапентин', type: 'Капсула', form_factor: 'tablet', strength: '300 мг', dose_unit: 'капс', default_dose: 0.1 },
    { name: 'Мелоксидил', type: 'Суспензия', form_factor: 'liquid', strength: '0.5 мг/мл', dose_unit: 'мл', default_dose: 2.5 },
    { name: 'Преднизолон', type: 'Таблетка', form_factor: 'tablet', strength: '5 мг', dose_unit: 'таб', default_dose: 1 },
    { name: 'Онсиор', type: 'Таблетка', form_factor: 'tablet', strength: '6 мг', dose_unit: 'таб', default_dose: 1 },
    { name: 'Доксициклин', type: 'Таблетка', form_factor: 'tablet', strength: '100 мг', dose_unit: 'таб', default_dose: 0.5 },
];

export interface MedicationIntake {
    _id: string;
    medication_id: string;
    pet_id: string;
    date_time: string;
    dose_taken: number;
    username: string;
    comment?: string;
}

export interface UpcomingDose {
    medication_id: string;
    name: string;
    type: string;
    time: string;
    date: string;
    is_overdue: boolean;
    inventory_warning: boolean;
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

    /** Always records the dose; ``ran_out`` says the stock is now empty. */
    async logIntake(id: string, data: { date: string; time: string; dose_taken?: number; comment?: string }): Promise<{ ran_out: boolean }> {
        const response = await api.post<{ ran_out?: boolean }>(`/medications/${id}/log`, data);
        return { ran_out: !!response.data.ran_out };
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
    };
}
