import api from './api';

export const exportService = {
  exportData: async (petId: string, exportType: string, format: 'csv' | 'tsv' | 'html' | 'md') => {
    try {
      const response = await api.get(`/export/${exportType}/${format}`, {
        params: { pet_id: petId },
        responseType: 'blob',
        // withCredentials: true is already in api instance
      });

      // Extract filename from Content-Disposition header
      const contentDisposition = response.headers['content-disposition'];
      let filename = `${exportType}_export.${format}`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/i);
        if (filenameMatch && filenameMatch[1]) {
          filename = decodeURIComponent(filenameMatch[1]);
        }
      }

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      return true;
    } catch (error) {
      console.error('Export failed:', error);
      throw error;
    }
  }
};
