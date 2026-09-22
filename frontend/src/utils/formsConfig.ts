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

/** Remembered default values for the builtin types' own fields, edited on
 *  the "Значения по умолчанию" settings page and applied when a new
 *  record of that type is opened. Custom types don't get this — there's
 *  no fixed field set to hang a default on ahead of time. */
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
