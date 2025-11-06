import axios, { AxiosError, AxiosInstance, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL, STORAGE_KEYS, MESSAGES } from '../utils/constants';
import { ApiError } from '../utils/types';

// Create axios instance
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request interceptor - add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors globally
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response;
  },
  (error: AxiosError<ApiError>) => {
    const apiError: ApiError = {
      message: MESSAGES.ERROR.GENERIC,
      status: error.response?.status,
    };

    if (error.response) {
      // Server responded with error
      apiError.message = error.response.data?.message || MESSAGES.ERROR.GENERIC;
      apiError.errors = error.response.data?.errors;

      // Handle unauthorized
      if (error.response.status === 401) {
        localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.USER);
        window.location.href = '/login';
      }
    } else if (error.request) {
      // Request made but no response
      apiError.message = MESSAGES.ERROR.NETWORK;
    }

    return Promise.reject(apiError);
  }
);

export default apiClient;

