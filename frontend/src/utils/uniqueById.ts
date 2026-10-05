/** The first of each `_id`, in order. A list read page by page by offset repeats the last items of a page when new records
    arrived meanwhile (the next page starts that many records later in the list than the person's page ended): a second card
    of the same record, and two children with one key. The next refresh makes the list whole again. */
export function uniqueById<T extends { _id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item._id)) return false;
    seen.add(item._id);
    return true;
  });
}
