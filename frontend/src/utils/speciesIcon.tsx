import { Cat, Dog, Bird, Fish, PawPrint, type LucideIcon } from 'lucide-react';

/**
 * Map a pet species string (free-form from the backend, set when the
 * user adds the pet) to a lucide line-art icon for placeholders and
 * species-only displays. Unknown values fall back to PawPrint so the
 * surface never looks empty.
 */
export function speciesIcon(species?: string | null): LucideIcon {
    if (!species) return PawPrint;
    const s = species.toLowerCase();
    if (s.includes('cat') || s.includes('кот') || s.includes('кош')) return Cat;
    if (s.includes('dog') || s.includes('собак') || s.includes('пёс') || s.includes('пес')) return Dog;
    if (s.includes('bird') || s.includes('птиц') || s.includes('попуг')) return Bird;
    if (s.includes('fish') || s.includes('рыб')) return Fish;
    return PawPrint;
}
