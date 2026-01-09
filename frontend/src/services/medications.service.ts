import api from './api';

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
    inventory_warning_threshold?: number;
    is_active: boolean;
    comment?: string;
    last_taken_at?: string;
    intakes_today?: number;
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
    async getList(petId: string): Promise<Medication[]> {
        const response = await api.get<{ medications: Medication[] }>('/medications', {
            params: { pet_id: petId }
        });
        return response.data.medications;
    },

    async create(data: MedicationCreate): Promise<string> {
        const response = await api.post<{ id: string }>('/medications', data);
        return response.data.id;
    },

    async update(id: string, data: Partial<MedicationCreate>): Promise<void> {
        await api.patch(`/medications/${id}`, data);
    },

    async delete(id: string): Promise<void> {
        await api.delete(`/medications/${id}`);
    },

    async logIntake(id: string, data: { date: string; time: string; dose_taken?: number; comment?: string }): Promise<void> {
        await api.post(`/medications/${id}/log`, data);
    },

    async getUpcoming(petId: string): Promise<UpcomingDose[]> {
        const response = await api.get<{ doses: UpcomingDose[] }>('/medications/upcoming', {
            params: { pet_id: petId }
        });
        return response.data.doses;
    }
};
