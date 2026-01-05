import { useCallback, useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { usePet } from './usePet';
import { DEFAULT_TILES_SETTINGS } from '../utils/tilesConfig';
import type { TilesSettings } from '../utils/tilesConfig';
import { petsService } from '../services/pets.service';

export function usePetTilesSettings(petId: string | null) {
  const { pets } = usePet();
  const queryClient = useQueryClient();

  const pet = useMemo(() => {
    if (!petId) return null;
    return pets.find(p => p._id === petId) || null;
  }, [petId, pets]);
  
  // Get tiles settings from pet or use default
  const tilesSettings: TilesSettings = useMemo(() => {
    if (pet?.tiles_settings) {
      return pet.tiles_settings;
    }
    return DEFAULT_TILES_SETTINGS;
  }, [pet]);

  const updateTilesSettingsMutation = useMutation({
    mutationFn: async (newSettings: TilesSettings) => {
      if (!petId || !pet) {
        throw new Error('Pet not selected');
      }
      return petsService.updatePet(petId, { tiles_settings: newSettings });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pets'] });
    },
  });

  const updateOrder = useCallback(
    (order: string[]) => {
      const newSettings: TilesSettings = {
        ...tilesSettings,
        order,
      };
      updateTilesSettingsMutation.mutate(newSettings);
    },
    [tilesSettings, updateTilesSettingsMutation]
  );

  const toggleVisibility = useCallback(
    (tileId: string, visible: boolean) => {
      const newSettings: TilesSettings = {
        ...tilesSettings,
        visible: {
          ...tilesSettings.visible,
          [tileId]: visible,
        },
      };
      updateTilesSettingsMutation.mutate(newSettings);
    },
    [tilesSettings, updateTilesSettingsMutation]
  );

  const resetSettings = useCallback(() => {
    updateTilesSettingsMutation.mutate(DEFAULT_TILES_SETTINGS);
  }, [updateTilesSettingsMutation]);

  return {
    tilesSettings,
    updateOrder,
    toggleVisibility,
    resetSettings,
    isLoading: updateTilesSettingsMutation.isPending,
  };
}

