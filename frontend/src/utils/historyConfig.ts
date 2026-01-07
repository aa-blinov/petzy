import type { TileColor, HealthRecordType } from './constants';

export interface HistoryItem {
  _id: string;
  date_time: string;
  username?: string;
  [key: string]: any;
}

export interface HistoryTypeConfig {
  endpoint: string;
  dataKey: string;
  displayName: string;
  color: TileColor;
  renderDetails: (item: HistoryItem) => string;
}

export const historyConfig: Record<HealthRecordType | 'asthma', HistoryTypeConfig> = {
  feeding: {
    endpoint: 'feeding',
    dataKey: 'feedings',
    displayName: 'Дневные порции',
    color: 'brown',
    renderDetails: (item) => {
      let html = `<span><strong>Вес корма:</strong> ${item.food_weight} г</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  asthma: {
    endpoint: 'asthma',
    dataKey: 'attacks',
    displayName: 'Приступы астмы',
    color: 'red',
    renderDetails: (item) => {
      let html = `<span><strong>Длительность:</strong> ${item.duration}</span>`;
      html += `<span><strong>Причина:</strong> ${item.reason}</span>`;
      const inhalationText = [true, 'true', 'Да'].includes(item.inhalation) ? 'Да' : 'Нет';
      html += `<span><strong>Ингаляция:</strong> ${inhalationText}</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  defecation: {
    endpoint: 'defecation',
    dataKey: 'defecations',
    displayName: 'Дефекации',
    color: 'green',
    renderDetails: (item) => {
      let html = `<span><strong>Тип стула:</strong> ${item.stool_type}</span>`;
      if (item.color) {
        html += `<span><strong>Цвет стула:</strong> ${item.color}</span>`;
      }
      if (item.food && item.food !== '-') {
        html += `<span><strong>Корм:</strong> ${item.food}</span>`;
      }
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  litter: {
    endpoint: 'litter',
    dataKey: 'litter_changes',
    displayName: 'Смена лотка',
    color: 'purple',
    renderDetails: (item) => {
      let html = '';
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  weight: {
    endpoint: 'weight',
    dataKey: 'weights',
    displayName: 'Вес',
    color: 'orange',
    renderDetails: (item) => {
      let html = `<span><strong>Вес:</strong> ${item.weight} кг</span>`;
      if (item.food && item.food !== '-') {
        html += `<span><strong>Корм:</strong> ${item.food}</span>`;
      }
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  eye_drops: {
    endpoint: 'eye_drops',
    dataKey: 'eye_drops',
    displayName: 'Глаза',
    color: 'teal',
    renderDetails: (item) => {
      let html = `<span><strong>Тип капель:</strong> ${item.drops_type}</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  tooth_brushing: {
    endpoint: 'tooth_brushing',
    dataKey: 'tooth_brushing',
    displayName: 'Зубы',
    color: 'cyan',
    renderDetails: (item) => {
      let html = `<span><strong>Способ чистки:</strong> ${item.brushing_type}</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  ear_cleaning: {
    endpoint: 'ear_cleaning',
    dataKey: 'ear_cleaning',
    displayName: 'Уши',
    color: 'yellow',
    renderDetails: (item) => {
      let html = `<span><strong>Способ чистки:</strong> ${item.cleaning_type}</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  },
  medications: {
    endpoint: 'medications/intakes',
    dataKey: 'intakes',
    displayName: 'Препараты',
    color: 'purple',
    renderDetails: (item: HistoryItem) => {
      let html = `<span><strong>Препарат:</strong> ${item.medication_name || 'Неизвестно'}</span>`;
      html += `<span><strong>Доза:</strong> ${item.dose_taken}</span>`;
      if (item.comment && item.comment !== '-') {
        html += `<span><strong>Комментарий:</strong> ${item.comment}</span>`;
      }
      return html;
    }
  }
};

export function formatDateTime(dateTimeStr: string): string {
  if (!dateTimeStr) return '';
  const parts = dateTimeStr.split(' ');
  if (parts.length !== 2) return dateTimeStr;
  const [datePart, timePart] = parts;
  const dateParts = datePart.split('-');
  if (dateParts.length !== 3) return dateTimeStr;
  const [year, month, day] = dateParts;
  return `${day}.${month}.${year} ${timePart}`;
}

