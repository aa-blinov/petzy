/**
 * Standalone editor for the diary tiles of the currently selected pet.
 *
 * It used to keep its own copy of the drag-and-drop list and persist to
 * a device-wide `tilesSettings` key in localStorage, while the quick-add
 * sheet and the history filter chips read the pet's `tiles_settings`
 * from the API — so nothing this screen did ever reached the UI. Both it
 * and the section inside the pet form now render the same TilesEditor
 * over the pet's own settings.
 */

import { useNavigate } from 'react-router-dom';
import { Button } from 'antd-mobile';

import { showToast } from '../utils/toast';
import { usePet } from '../hooks/usePet';
import { usePetTilesSettings } from '../hooks/usePetTilesSettings';
import { TilesEditor } from '../components/TilesEditor';
import { EmptyState } from '../components/EmptyState';
import { LayoutGrid } from 'lucide-react';

export function TilesSettings() {
  const navigate = useNavigate();
  const { selectedPetId, selectedPetName } = usePet();
  const { resetSettings } = usePetTilesSettings(selectedPetId);

  const handleReset = () => {
    if (!window.confirm('Сбросить порядок и видимость тайлов к значениям по умолчанию?')) return;
    try {
      resetSettings();
      showToast.success('Настройки тайлов сброшены');
    } catch {
      showToast.failure('Не удалось сбросить настройки');
    }
  };

  return (
    <div className="page-container">
      <div className="max-width-container">
        <div className="safe-area-padding" style={{ marginBottom: 'var(--spacing-lg)' }}>
          <h2 style={{ color: 'var(--app-text-color)', fontSize: 'var(--text-xxl)', fontWeight: 600, margin: 0 }}>
            Порядок тайлов
          </h2>
          <p style={{ margin: 'var(--spacing-sm) 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--app-text-secondary)' }}>
            {/* Naming the pet matters now that the settings really are
                per-pet: without it, switching pets would silently change
                what this screen edits. */}
            {selectedPetName
              ? <>Настройки для питомца <strong>{selectedPetName}</strong>. Перетащите, чтобы изменить порядок, переключатель скрывает тайл. Изменения сохраняются сразу.</>
              : 'Перетащите, чтобы изменить порядок, переключатель скрывает тайл.'}
          </p>
        </div>

        {!selectedPetId ? (
          <EmptyState
            icon={LayoutGrid}
            title="Сначала выберите питомца"
            description="Тайлы дневника настраиваются отдельно для каждого питомца."
            actionLabel="К питомцам"
            onAction={() => navigate('/pets')}
          />
        ) : (
          <>
            <TilesEditor petId={selectedPetId} mode="card" />

            <div className="safe-area-padding" style={{
              paddingTop: 'var(--spacing-lg)',
              paddingBottom: 'var(--spacing-lg)',
              display: 'flex',
              flexDirection: 'column',
              gap: 'var(--spacing-md)',
            }}>
              {/* No "Save": every toggle and drop persists on the spot,
                  so a save button would only be able to lie. */}
              <Button
                block
                color="default"
                size="large"
                onClick={handleReset}
                style={{ borderRadius: 'var(--radius-md)', fontWeight: 500 }}
              >
                Сбросить к значениям по умолчанию
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
