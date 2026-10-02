import { isAxiosError } from 'axios';
import api from './api';
import { deviceTimeZone } from '../utils/timezone';
import { saveBlob } from '../utils/download';

export type ExportFormat = 'csv' | 'tsv' | 'html' | 'md';

export const exportService = {
  exportData: async (petId: string, exportType: string, format: ExportFormat) => {
    try {
      const response = await api.get(`/export/${exportType}/${format}`, {
        // The exporter's zone: the times in the file are shown on this clock.
        params: { pet_id: petId, tz: deviceTimeZone() },
        responseType: 'blob',
        // withCredentials: true is already in api instance
      });

      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers['content-disposition'];
      // The all-types export arrives as a ZIP of per-type files, so the
      // fallback name must not claim the requested text format.
      const fallbackExt = exportType === 'all' ? 'zip' : format;
      let filename = `${exportType}_export.${fallbackExt}`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
        if (filenameMatch && filenameMatch[1]) {
          filename = decodeURIComponent(filenameMatch[1]);
        }
      }

      saveBlob(response.data, filename);

      return true;
    } catch (error) {
      console.error('Export failed:', error);
      // The body of a failed download is a blob too: the server's own words (there is nothing to export) are read out of it.
      if (isAxiosError(error) && error.response?.data instanceof Blob) {
        try {
          const body = JSON.parse(await error.response.data.text()) as { error?: string };
          if (body.error) error.response.data = { error: body.error };
        } catch {
          /* not JSON: the usual message applies */
        }
      }
      throw error;
    }
  }
};
