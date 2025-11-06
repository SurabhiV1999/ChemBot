import apiClient from './client';
import { API_ENDPOINTS } from '../utils/constants';
import { Content, UploadContentResponse } from '../utils/types';

export const contentApi = {
  upload: async (file: File, title: string): Promise<UploadContentResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);

    const response = await apiClient.post<UploadContentResponse>(
      API_ENDPOINTS.CONTENT.UPLOAD,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },

  list: async (): Promise<Content[]> => {
    const response = await apiClient.get<Content[]>(API_ENDPOINTS.CONTENT.LIST);
    return response.data;
  },

  get: async (id: string): Promise<Content> => {
    const response = await apiClient.get<Content>(API_ENDPOINTS.CONTENT.GET(id));
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.CONTENT.DELETE(id));
  },
};

