/** Monday to Sunday, as the schedule keeps them (0 is Monday). */
export const ALL_WEEKDAYS = [0, 1, 2, 3, 4, 5, 6];

/** What a new course starts with: given every day (narrowing the week is the optional part) and begun today,
 *  as the record forms start from today. A course being edited starts from what is saved instead. */
export function newCourseDefaults(today: string): { days: number[]; started_on: string } {
  return { days: [...ALL_WEEKDAYS], started_on: today };
}
