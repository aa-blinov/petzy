import type { TileColor } from './constants';

export interface TileConfig {
  id: string;
  title: string;
  subtitle: string;
  color: TileColor;
  screen: string;
  isAdmin?: boolean;
}

export const tilesConfig: TileConfig[] = [
  { id: 'feeding', title: 'Дневная порция корма', subtitle: 'Записать порцию', color: 'brown', screen: 'feeding-form' },
  { id: 'weight', title: 'Вес', subtitle: 'Записать вес', color: 'orange', screen: 'weight-form' },
  { id: 'asthma', title: 'Приступ астмы', subtitle: 'Записать приступ', color: 'red', screen: 'asthma-form' },
  { id: 'defecation', title: 'Дефекация', subtitle: 'Записать дефекацию', color: 'green', screen: 'defecation-form' },
  { id: 'litter', title: 'Смена лотка', subtitle: 'Записать смену лотка', color: 'purple', screen: 'litter-form' },
  { id: 'eye_drops', title: 'Закапывание глаз', subtitle: 'Записать капли', color: 'teal', screen: 'eye-drops-form' },
  { id: 'tooth_brushing', title: 'Чистка зубов', subtitle: 'Записать чистку', color: 'cyan', screen: 'tooth-brushing-form' },
  { id: 'ear_cleaning', title: 'Чистка ушей', subtitle: 'Записать чистку', color: 'yellow', screen: 'ear-cleaning-form' }
];

export interface TilesSettings {
  order: string[];
  visible: Record<string, boolean>;
}

export const DEFAULT_TILES_SETTINGS: TilesSettings = {
  // Sort tiles alphabetically by title by default (Russian alphabet order)
  // Order: Вес, Дефекация, Дневная порция корма, Закапывание глаз, Приступ астмы, Смена лотка, Чистка ушей, Чистка зубов
  order: [
    'weight',        // Вес
    'defecation',    // Дефекация
    'feeding',       // Дневная порция корма
    'eye_drops',     // Закапывание глаз
    'asthma',        // Приступ астмы
    'litter',        // Смена лотка
    'ear_cleaning',  // Чистка ушей
    'tooth_brushing' // Чистка зубов
  ],
  visible: tilesConfig.reduce((acc, tile) => {
    acc[tile.id] = true;
    return acc;
  }, {} as Record<string, boolean>)
};

