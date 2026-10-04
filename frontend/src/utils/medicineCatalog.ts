import type { ProductGroup } from '../components/ProductPickerSheet';

/**
 * The medicines the list offers to search, by what they are for. Only names, to save typing: a medicine that is not here is typed
 * (a list cannot hold every one), and the dose and the schedule are the vet's. A few are known with their form and the strength of
 * the box (COMMON_MEDICATIONS in the service), and those fill the form in when chosen.
 */
export const MEDICINE_GROUPS: ProductGroup[] = [
  { key: 'pain', label: 'Боль и воспаление', items: ['Мелоксидил', 'Метакам', 'Онсиор', 'Римадил', 'Преднизолон'] },
  { key: 'antibiotic', label: 'Антибиотики', items: ['Синулокс 50мг', 'Синулокс 250мг', 'Доксициклин', 'Амоксиклав', 'Метронидазол'] },
  { key: 'nerve', label: 'Нервная система', items: ['Габапентин'] },
  { key: 'stomach', label: 'Желудок и рвота', items: ['Омепразол', 'Фамотидин', 'Церения'] },
  { key: 'joints', label: 'Суставы', items: ['Глюкозамин', 'Хондроитин'] },
  { key: 'heart', label: 'Сердце и давление', items: ['Ветмедин', 'Фуросемид', 'Эналаприл'] },
  { key: 'parasites', label: 'Паразиты', items: ['Дронтал Плюс', 'Мильбемакс', 'Бравекто', 'Нексгард', 'Симпарика'] },
];
