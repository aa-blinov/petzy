import { useCallback } from 'react';
import { useLocalStorage } from './useLocalStorage';
import { DEFAULT_TILES_SETTINGS } from '../utils/tilesConfig';
import type { TilesSettings } from '../utils/tilesConfig';

export function useTilesSettings() {
  const [tilesSettings, setTilesSettings] = useLocalStorage<TilesSettings>(
    'tilesSettings',
    DEFAULT_TILES_SETTINGS
  );

  const updateOrder = useCallback((order: string[]) => {
    setTilesSettings({
      ...tilesSettings,
      order
    });
  }, [tilesSettings, setTilesSettings]);

  const toggleVisibility = useCallback((tileId: string, visible: boolean) => {
    setTilesSettings({
      ...tilesSettings,
      visible: {
        ...tilesSettings.visible,
        [tileId]: visible
      }
    });
  }, [tilesSettings, setTilesSettings]);

  const resetSettings = useCallback(() => {
    setTilesSettings(DEFAULT_TILES_SETTINGS);
  }, [setTilesSettings]);

  return {
    tilesSettings,
    updateOrder,
    toggleVisibility,
    resetSettings
  };
}

