import type { HealthRecordType } from './constants';

export interface FormFieldOption {
  value: string;
  text: string;
}

export interface FormField {
  name: string;
  type: 'date' | 'time' | 'text' | 'number' | 'select' | 'textarea';
  label: string;
  required?: boolean;
  placeholder?: string;
  value?: string;
  min?: number;
  max?: number;
  step?: number;
  rows?: number;
  options?: FormFieldOption[];
  id: string;
}

export interface FormConfig {
  title: string;
  endpoint: string;
  fields: FormField[];
  transformData: (data: Record<string, any>) => Record<string, any>;
  successMessage: (isEdit: boolean) => string;
}

export type FormConfigs = Record<HealthRecordType, FormConfig>;

export const formConfigs: FormConfigs = {
  feeding: {
    title: 'Записать дневную порцию корма',
    endpoint: '/api/feeding',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'feeding-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'feeding-time' },
      { name: 'food_weight', type: 'number', label: 'Вес корма (граммы)', required: true, placeholder: '50', min: 0, step: 0.1, id: 'feeding-food-weight' },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'feeding-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      food_weight: data.food_weight,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Дневная порция обновлена' : 'Дневная порция записана'
  },
  asthma: {
    title: 'Записать приступ астмы',
    endpoint: '/api/asthma',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'asthma-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'asthma-time' },
      {
        name: 'duration', type: 'select', label: 'Длительность', required: true, options: [
          { value: 'Короткий', text: 'Короткий' },
          { value: 'Длительный', text: 'Длительный' }
        ], value: 'Короткий', id: 'asthma-duration'
      },
      {
        name: 'inhalation', type: 'select', label: 'Ингаляция', required: true, options: [
          { value: 'false', text: 'Нет' },
          { value: 'true', text: 'Да' }
        ], value: 'false', id: 'asthma-inhalation'
      },
      { name: 'reason', type: 'text', label: 'Причина', required: true, placeholder: 'Пил после сна', value: 'Пил', id: 'asthma-reason' },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'asthma-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      duration: data.duration,
      reason: data.reason,
      inhalation: data.inhalation === 'true' || data.inhalation === true,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Приступ астмы обновлен' : 'Приступ астмы записан'
  },
  defecation: {
    title: 'Записать дефекацию',
    endpoint: '/api/defecation',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'defecation-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'defecation-time' },
      {
        name: 'stool_type', type: 'select', label: 'Тип стула', required: true, options: [
          { value: 'Обычный', text: 'Обычный' },
          { value: 'Твердый', text: 'Твердый' },
          { value: 'Жидкий', text: 'Жидкий' }
        ], value: 'Обычный', id: 'defecation-stool-type'
      },
      {
        name: 'color', type: 'select', label: 'Цвет стула', required: true, options: [
          { value: 'Коричневый', text: 'Коричневый' },
          { value: 'Темно-коричневый', text: 'Темно-коричневый' },
          { value: 'Светло-коричневый', text: 'Светло-коричневый' },
          { value: 'Другой', text: 'Другой' }
        ], value: 'Коричневый', id: 'defecation-color'
      },
      { name: 'food', type: 'text', label: 'Корм', placeholder: 'Royal Canin Fibre Response', value: 'Royal Canin Fibre Response', id: 'defecation-food' },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'defecation-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      stool_type: data.stool_type,
      color: data.color,
      food: data.food || '',
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Дефекация обновлена' : 'Дефекация записана'
  },
  litter: {
    title: 'Записать смену лотка',
    endpoint: '/api/litter',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'litter-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'litter-time' },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 3, placeholder: 'Полная замена наполнителя', id: 'litter-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Смена лотка обновлена' : 'Смена лотка записана'
  },
  weight: {
    title: 'Записать вес',
    endpoint: '/api/weight',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'weight-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'weight-time' },
      { name: 'weight', type: 'number', label: 'Вес (кг)', required: true, placeholder: '4.5', step: 0.01, min: 0, id: 'weight-value' },
      { name: 'food', type: 'text', label: 'Корм', placeholder: 'Royal Canin Fibre Response', value: 'Royal Canin Fibre Response', id: 'weight-food' },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'weight-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      weight: data.weight,
      food: data.food || '',
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Вес обновлен' : 'Вес записан'
  },
  eye_drops: {
    title: 'Записать закапывание глаз',
    endpoint: '/api/eye_drops',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'eye-drops-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'eye-drops-time' },
      {
        name: 'drops_type', type: 'select', label: 'Тип капель', required: true, options: [
          { value: 'Обычные', text: 'Обычные' },
          { value: 'Гелевые', text: 'Гелевые' }
        ], value: 'Обычные', id: 'eye-drops-type'
      },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'eye-drops-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      drops_type: data.drops_type,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Запись о каплях обновлена' : 'Запись о каплях создана'
  },
  tooth_brushing: {
    title: 'Записать чистку зубов',
    endpoint: '/api/tooth_brushing',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'tooth-brushing-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'tooth-brushing-time' },
      {
        name: 'brushing_type', type: 'select', label: 'Способ чистки', required: true, options: [
          { value: 'Щетка', text: 'Щетка' },
          { value: 'Марля', text: 'Марля' },
          { value: 'Игрушка', text: 'Игрушка' }
        ], value: 'Щетка', id: 'tooth-brushing-type'
      },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'tooth-brushing-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      brushing_type: data.brushing_type,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Запись о чистке зубов обновлена' : 'Запись о чистке зубов создана'
  },
  ear_cleaning: {
    title: 'Записать чистку ушей',
    endpoint: '/api/ear_cleaning',
    fields: [
      { name: 'date', type: 'date', label: 'Дата', required: true, id: 'ear-cleaning-date' },
      { name: 'time', type: 'time', label: 'Время', required: true, id: 'ear-cleaning-time' },
      {
        name: 'cleaning_type', type: 'select', label: 'Способ чистки', required: true, options: [
          { value: 'Салфетка/Марля', text: 'Салфетка/Марля' },
          { value: 'Капли', text: 'Капли' }
        ], value: 'Салфетка/Марля', id: 'ear-cleaning-type'
      },
      { name: 'comment', type: 'textarea', label: 'Комментарий (необязательно)', rows: 2, id: 'ear-cleaning-comment' }
    ],
    transformData: (data) => ({
      pet_id: data.pet_id,
      date: data.date,
      time: data.time,
      cleaning_type: data.cleaning_type,
      comment: data.comment || ''
    }),
    successMessage: (isEdit) => isEdit ? 'Запись о чистке ушей обновлена' : 'Запись о чистке ушей создана'
  },
  medications: {
    title: 'Препараты',
    endpoint: '/api/medications',
    fields: [], // Medications has its own complex form MedicationForm.tsx
    transformData: (data) => data,
    successMessage: (isEdit) => isEdit ? 'Препарат обновлен' : 'Препарат добавлен'
  }
};

export interface FormSettings {
  asthma?: {
    duration?: string;
    inhalation?: string;
    reason?: string;
  };
  defecation?: {
    stool_type?: string;
    color?: string;
    food?: string;
  };
  weight?: {
    food?: string;
  };
  eye_drops?: {
    drops_type?: string;
  };
  tooth_brushing?: {
    brushing_type?: string;
  };
  ear_cleaning?: {
    cleaning_type?: string;
  };
}

export const DEFAULT_FORM_SETTINGS: FormSettings = {
  asthma: {
    duration: 'Короткий',
    inhalation: 'false',
    reason: 'Пил'
  },
  defecation: {
    stool_type: 'Обычный',
    color: 'Коричневый',
    food: 'Royal Canin Fibre Response'
  },
  weight: {
    food: 'Royal Canin Fibre Response'
  },
  eye_drops: {
    drops_type: 'Обычные'
  },
  tooth_brushing: {
    brushing_type: 'Щетка'
  },
  ear_cleaning: {
    cleaning_type: 'Салфетка/Марля'
  }
};

export function getFormSettings(): FormSettings {
  try {
    const saved = localStorage.getItem('formDefaults');
    if (saved) {
      const settings = JSON.parse(saved) as FormSettings;
      // Ensure backward compatibility
      if (settings.defecation && !settings.defecation.color) {
        settings.defecation.color = 'Коричневый';
      }
      return settings;
    }
  } catch (e) {
    console.error('Error loading settings:', e);
  }
  return DEFAULT_FORM_SETTINGS;
}

