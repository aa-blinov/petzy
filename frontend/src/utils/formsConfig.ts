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

/** Remembered default values for a pet's builtin types' own fields, edited on
 *  the "Значения по умолчанию" settings page (or by the switch at the foot of a new record's form), kept on the pet and
 *  applied when a new record of that type is opened. Custom types don't get this — there's
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

/** The fields of each built-in type that can have a default: the same ones «Значения по умолчанию» offers. A form of a new
 *  record can save what was typed into them as the default (the switch at its foot). */
export const DEFAULTABLE_FIELDS: Record<string, string[]> = {
  asthma: ['duration', 'inhalation', 'reason'],
  defecation: ['stool_type', 'color', 'food'],
  weight: ['food'],
  eye_drops: ['drops_type'],
  tooth_brushing: ['brushing_type'],
  ear_cleaning: ['cleaning_type'],
};

/** Nothing is filled in until the person sets it themselves on «Значения по умолчанию»: a built-in value (a food
 *  brand, a stool colour, a reason) would be recorded as if the family had typed it, and the diary is shown to a vet. */
export const DEFAULT_FORM_SETTINGS: FormSettings = {};
