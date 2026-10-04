import { useQuery } from '@tanstack/react-query';

import { vaccinesService, type VaccineCatalog, type VaccineProduct } from '../services/vaccines.service';

/** The vaccines the form offers to search, with what each is against. The same list for everyone and for a long while, asked once. */
export function useVaccineCatalog() {
  return useQuery({ queryKey: ['vaccine-catalog'], queryFn: vaccinesService.catalog, staleTime: Infinity, gcTime: Infinity });
}

/** The species code the catalogue is sorted by: a pet of a kind it has no list for gets the general one. */
export function catalogSpecies(species: string | undefined): string {
  return species === 'dog' || species === 'cat' || species === 'rabbit' ? species : 'other';
}

const norm = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();

/** What a typed name is against, if it is one the catalogue knows (a start of it, so «Нобивак DHPPi (2025)» is read too);
    the longest known name wins, so that «Нобивак DHPPi» is not taken for «Нобивак DHP». */
export function inferProtects(title: string, catalog: VaccineCatalog | undefined, species: string): string | null {
  const name = norm(title);
  if (!name || !catalog) return null;
  const known: VaccineProduct[] = catalog.products.filter((p) => p.species.includes(species) && p.name !== 'Комплексная прививка');
  const found = known
    .filter((p) => {
      const n = norm(p.name);
      return name === n || name.startsWith(`${n} `) || name.startsWith(`${n}(`);
    })
    .sort((a, b) => b.name.length - a.name.length)[0];
  return found?.protects ?? null;
}
