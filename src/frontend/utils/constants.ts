// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// API Endpoints
export const API_ENDPOINTS = {
  AUTH: {
    LOGIN: '/auth/login',
    LOGOUT: '/auth/logout',
    REGISTER: '/auth/register',
    ME: '/auth/me',
  },
  CONTENT: {
    UPLOAD: '/content/upload',
    LIST: '/content/',
    GET: (id: string) => `/content/${id}`,
    DELETE: (id: string) => `/content/${id}`,
  },
  CHAT: {
    ASK: (contentId: string) => `/content/${contentId}/question`,
    HISTORY: (contentId: string) => `/content/${contentId}/questions`,
  },
  ANALYTICS: {
    STUDENT: (userId: string) => `/analytics/student/${userId}`,
  },
} as const;

// Local Storage Keys
export const STORAGE_KEYS = {
  AUTH_TOKEN: 'chembot_auth_token',
  USER: 'chembot_user',
} as const;

// File Upload Configuration
export const FILE_UPLOAD = {
  MAX_SIZE: 10 * 1024 * 1024, // 10MB
  ACCEPTED_TYPES: [
    'application/pdf',
    'text/plain',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/markdown',
  ],
  ACCEPTED_EXTENSIONS: ['.pdf', '.txt', '.docx', '.md'],
} as const;

// UI Configuration
export const UI_CONFIG = {
  TOAST_DURATION: 5000,
  DEBOUNCE_DELAY: 300,
} as const;

// Message Templates
export const MESSAGES = {
  ERROR: {
    GENERIC: 'An error occurred. Please try again.',
    NETWORK: 'Network error. Please check your connection.',
    UNAUTHORIZED: 'Please login to continue.',
    FILE_TOO_LARGE: `File size exceeds ${FILE_UPLOAD.MAX_SIZE / 1024 / 1024}MB limit.`,
    INVALID_FILE_TYPE: 'Invalid file type. Please upload PDF, TXT, DOCX, or MD files.',
  },
  SUCCESS: {
    LOGIN: 'Successfully logged in!',
    LOGOUT: 'Successfully logged out!',
    UPLOAD: 'Content uploaded successfully!',
    DELETE: 'Content deleted successfully!',
  },
} as const;

