/**
 * The feed's «+»: the pet's record types as tiles, plus the doors to the clinical records, the rest of the catalogue and the
 * settings of the window. It is the shared AddSheet, the same look as the medical card's and the Documents'.
 */

import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { buildTiles, byTileOrder, isTileShown } from '../utils/tilesConfig';
import { buildEventDisplayConfigs } from '../utils/eventDisplay';
import { getSpecies, suggestedFirst } from '../utils/species';
import { useEventTypes } from '../hooks/useEventTypes';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { usePet } from '../hooks/usePet';
import { AddLink, AddSheet, AddTile, AddTiles } from './AddSheet';

interface QuickAddSheetProps {
  visible: boolean;
  onClose: () => void;
}

export function QuickAddSheet({ visible, onClose }: QuickAddSheetProps) {
  const navigate = useNavigate();
  const { selectedPetId, getSelectedPet } = usePet();
  const { tilesSettings } = usePetTilesSettings(selectedPetId);
  const { eventTypes } = useEventTypes();
  const displayConfigs = useMemo(() => buildEventDisplayConfigs(eventTypes), [eventTypes]);

  const tiles = byTileOrder(
    buildTiles(eventTypes).filter((t) => t.isTile !== false && isTileShown(tilesSettings, t.id)),
    tilesSettings,
  );
  // The types this pet does not show as tiles: a one-off record of one of them is logged from here, without adding the type to
  // the pet first.
  // The ones that suit this kind of animal come first: a cat's list does not open on a terrarium's lamp.
  const others = suggestedFirst(
    buildTiles(eventTypes).filter((t) => t.isTile !== false && !isTileShown(tilesSettings, t.id)),
    getSpecies(getSelectedPet?.species).suggested,
  );
  const [othersOpen, setOthersOpen] = useState(false);
  const isOwner = getSelectedPet?.current_user_is_owner !== false;
  // The list of the others closes with the sheet: the next opening starts with the pet's own tiles.
  const close = () => {
    setOthersOpen(false);
    onClose();
  };

  const renderTiles = (list: typeof tiles) => (
    <AddTiles>
      {list.map((tile) => (
        <AddTile
          key={tile.id}
          label={tile.title}
          icon={displayConfigs[tile.id]?.icon}
          color={tile.color}
          badge={tile.custom ? 'Свой' : undefined}
          onClick={() => {
            close();
            navigate(`/form/${tile.id}`);
          }}
        />
      ))}
    </AddTiles>
  );

  return (
    <AddSheet visible={visible} onClose={close}>
      {tiles.length === 0 && (
        // Every tile is hidden in the settings: said, with the way back, not an empty sheet.
        <div className="addsheet__note">
          <p style={{ margin: '0 0 var(--spacing-md)' }}>В окне «+» ничего нет: добавьте типы записей питомца</p>
          <AddLink
            onClick={() => {
              close();
              navigate('/pet-events');
            }}
          >
            Добавить типы записей
          </AddLink>
        </div>
      )}

      {renderTiles(tiles)}

      {/* The clinical records (a vaccination, a treatment, a visit) are part of the pet's life too, and the diary's window is where a
          person looks first: one door to their own chooser, the medical card's records, not another tile among the diary's. */}
      {selectedPetId && (
        <AddLink
          onClick={() => {
            close();
            navigate(`/pets/${selectedPetId}/medical-records/new`);
          }}
        >
          Прививка, визит или обработка
        </AddLink>
      )}

      {/* A new pet starts with a few events; the rest of the catalogue is here, one tap from a record, for whoever may log. */}
      {tiles.length > 0 && others.length > 0 && !othersOpen && (
        <AddLink expanded={false} onClick={() => setOthersOpen(true)}>
          Другие записи
        </AddLink>
      )}
      {(othersOpen || (tiles.length === 0 && others.length > 0)) && (
        <>
          <h3 className="addsheet__subtitle">Другие записи</h3>
          {renderTiles(others)}
        </>
      )}
      {/* Which events stay in this window is the owner's to change. */}
      {tiles.length > 0 && isOwner && (
        <AddLink
          onClick={() => {
            close();
            navigate('/pet-events');
          }}
        >
          Настроить типы записей
        </AddLink>
      )}
    </AddSheet>
  );
}
