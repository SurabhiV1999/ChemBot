// User and Authentication Types
export interface User {
  id: string;
  email: string;
  name: string;
  role: 'student' | 'teacher';
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  token_type?: string;
}

// Content Types
export interface Content {
  id: string;
  title: string;
  fileName: string;
  fileSize: number;
  uploadedAt: string;
  status: 'processing' | 'ready' | 'error';
  userId: string;
}

export interface UploadContentResponse {
  content: Content;
  message: string;
}

// Chat Types
export interface Message {
  id: string;
  contentId: string;
  question: string;
  answer: string;
  timestamp: string;
  userId: string;
  cached?: boolean;
  confidence_score?: number;
}

export interface ChatRequest {
  contentId: string;
  question: string;
}

export interface ChatResponse {
  answer: string;
  message: Message;
  cached?: boolean;
  confidence_score?: number;
}

// API Response Types
export interface ApiError {
  message: string;
  status?: number;
  errors?: Record<string, string[]>;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

// UI State Types
export interface LoadingState {
  isLoading: boolean;
  message?: string;
}

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration?: number;
}

