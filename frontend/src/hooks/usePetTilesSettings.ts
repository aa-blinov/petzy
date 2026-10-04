import { useCallback, useMemo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { usePet } from './usePet';
import { DEFAULT_TILES_SETTINGS } from '../utils/tilesConfig';
import type { TilesSettings } from '../utils/tilesConfig';
import { petsService, type Pet } from '../services/pets.service';
import { showToast } from '../utils/toast';
import { getApiErrorMessage } from '../utils/apiError';

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
    // The change is on screen at once and the server confirms it after: a row dropped into place does not jump back first.
    onMutate: (newSettings: TilesSettings) => {
      queryClient.setQueryData<Pet[]>(['pets'], (all) => all?.map((p) => (p._id === petId ? { ...p, tiles_settings: newSettings } : p)));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pets'] });
    },
    // A refusal is said (the list snaps back to what the server has): silence read as a switch that does not work.
    onError: (err: unknown) => {
      queryClient.invalidateQueries({ queryKey: ['pets'] });
      showToast.failure(getApiErrorMessage(err, 'Не удалось сохранить плитки'));
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

  /** Replaces the pet's settings in one request (an event added is a change of both what is shown and where). */
  const saveSettings = useCallback(
    (next: TilesSettings) => updateTilesSettingsMutation.mutate(next),
    [updateTilesSettingsMutation],
  );

  const resetSettings = useCallback(() => {
    updateTilesSettingsMutation.mutate(DEFAULT_TILES_SETTINGS);
  }, [updateTilesSettingsMutation]);

  return {
    tilesSettings,
    updateOrder,
    toggleVisibility,
    saveSettings,
    resetSettings,
    isLoading: updateTilesSettingsMutation.isPending,
  };
}

