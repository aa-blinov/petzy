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

/** The fields a new record can remember a value for, for the pet it is written for: a choice, a word or a number. Not the date
 *  and the time, which are never the same twice, nor the comment. Any record type, built-in or the family's own. */
export const isDefaultableField = (field: { type: string }): boolean => ['select', 'text', 'number'].includes(field.type);

/** Nothing is filled in until the person sets it themselves on «Значения по умолчанию»: a built-in value (a food
 *  brand, a stool colour, a reason) would be recorded as if the family had typed it, and the diary is shown to a vet. */
export const DEFAULT_FORM_SETTINGS: FormSettings = {};
