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

/** What a new record of each type starts with for a pet: {type: {field: value}}. Any type, built-in or the family's own, any
 *  plain field of it. Kept on the pet; set by the pin under a field of a new record, looked at and corrected on «Значения по
 *  умолчанию». */
export type FormSettings = Record<string, Record<string, string>>;

/** The fields a new record can remember a value for, for the pet it is written for: a choice, a word or a number. Not the date
 *  and the time, which are never the same twice, nor the comment. Any record type, built-in or the family's own. */
export const isDefaultableField = (field: { type: string }): boolean => ['select', 'text', 'number'].includes(field.type);

/** Nothing is filled in until the person sets it themselves on «Значения по умолчанию»: a built-in value (a food
 *  brand, a stool colour, a reason) would be recorded as if the family had typed it, and the diary is shown to a vet. */
export const DEFAULT_FORM_SETTINGS: FormSettings = {};
