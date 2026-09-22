/** Best-effort Cyrillic → Latin transliteration, just enough to turn a
 *  human-typed field label into a valid, readable field name (the
 *  identifier stored in `event_types.fields[].name`). */
const CYRILLIC_MAP: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z',
  и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r',
  с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch',
  ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya',
};

function transliterate(text: string): string {
  return text
    .toLowerCase()
    .split('')
    .map((ch) => CYRILLIC_MAP[ch] ?? ch)
    .join('');
}

/** Turns a label into a `^[a-z][a-z0-9_]{0,49}$`-safe field name, unique
 *  against `existing`. Falls back to `field` when nothing alphabetic
 *  survives (e.g. a label made only of emoji or digits). */
export function slugifyFieldName(label: string, existing: string[] = []): string {
  let slug = transliterate(label)
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 50);

  if (!slug || !/^[a-z]/.test(slug)) {
    slug = `field_${slug}`.replace(/_+$/, '').slice(0, 50) || 'field';
  }

  let candidate = slug;
  let suffix = 2;
  while (existing.includes(candidate)) {
    candidate = `${slug}_${suffix}`.slice(0, 50);
    suffix += 1;
  }
  return candidate;
}
