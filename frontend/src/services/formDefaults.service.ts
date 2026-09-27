import api from './api';
import type { FormSettings } from '../utils/formsConfig';

/** «Настройки форм», kept on the account so every device shares them. */
export const formDefaultsService = {
    async get(): Promise<FormSettings> {
        const response = await api.get<{ form_defaults: FormSettings }>('/me/form-defaults');
        return response.data.form_defaults ?? {};
    },

    async save(settings: FormSettings): Promise<void> {
        await api.put('/me/form-defaults', { form_defaults: settings });
    },
};
