import { createElement, useState } from 'react';
import { Picker } from 'antd-mobile';
import { PawPrint } from 'lucide-react';

import { MORE_SPECIES, TILE_SPECIES, getSpecies, type SpeciesKey } from '../utils/species';
import './SpeciesTiles.css';

/**
 * The kind of animal, by picture: the common ones are a tile each and the rest are one tap away in «Другой». It is the same choice
 * as in the first-pet onboarding, and for the same reason: a wheel picker hides the options, and it opens already on «Кот», which
 * «Готово» then picks without the person having chosen anything.
 */
export function SpeciesTiles({ value, onChange }: { value?: string | null; onChange: (key: SpeciesKey) => void }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const chosen = value ? getSpecies(value) : null;
  const picked = chosen && !TILE_SPECIES.includes(chosen.key) ? chosen : null;

  return (
    <div role="group" aria-label="Вид питомца" className="species-tiles">
      {TILE_SPECIES.map((key) => {
        const s = getSpecies(key);
        return (
          <button key={key} type="button" className="species-tile tap-feedback" aria-pressed={chosen?.key === key} onClick={() => onChange(key)}>
            <span className="species-tile__icon" style={{ background: s.gradient }}>
              {createElement(s.icon, { size: 24, strokeWidth: 2, 'aria-hidden': true })}
            </span>
            {s.label}
          </button>
        );
      })}
      <button type="button" className="species-tile tap-feedback" aria-pressed={!!picked} aria-haspopup="dialog" onClick={() => setMoreOpen(true)}>
        <span className="species-tile__icon" style={{ background: (picked ?? getSpecies('other')).gradient }}>
          {createElement(picked?.icon ?? PawPrint, { size: 24, strokeWidth: 2, 'aria-hidden': true })}
        </span>
        {picked ? picked.label : 'Другой'}
      </button>
      <Picker
        columns={[MORE_SPECIES]}
        visible={moreOpen}
        value={picked ? [picked.key] : []}
        onClose={() => setMoreOpen(false)}
        onConfirm={(val) => {
          if (val[0]) onChange(val[0] as SpeciesKey);
          setMoreOpen(false);
        }}
        cancelText="Отмена"
        confirmText="Готово"
      />
    </div>
  );
}
