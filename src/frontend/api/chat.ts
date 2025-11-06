import apiClient from './client';
import { API_ENDPOINTS } from '../utils/constants';
import { ChatRequest, ChatResponse, Message } from '../utils/types';

export const chatApi = {
  askQuestion: async (request: ChatRequest, clearHistory: boolean = false): Promise<ChatResponse> => {
    const response = await apiClient.post<ChatResponse>(
      API_ENDPOINTS.CHAT.ASK(request.contentId),
      { 
        question: request.question,
        stream: false,
        clear_history: clearHistory
      }
    );
    return response.data;
  },

  askQuestionStream: async (
    request: ChatRequest,
    onChunk: (chunk: string) => void,
    onComplete: (fullAnswer: string) => void,
    onError: (error: string) => void,
    clearHistory: boolean = false
  ): Promise<void> => {
    try {
      const token = localStorage.getItem('chembot_auth_token');
      const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
      
      const response = await fetch(
        `${baseUrl}${API_ENDPOINTS.CHAT.ASK(request.contentId)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify({
            question: request.question,
            stream: true,
            clear_history: clearHistory
          }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = '';

      if (!reader) {
        throw new Error('Response body is not readable');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              
              if (data.chunk) {
                fullAnswer += data.chunk;
                onChunk(data.chunk);
              }
              
              if (data.done) {
                onComplete(data.full_answer || fullAnswer);
                return;
              }
              
              if (data.error) {
                onError(data.error);
                return;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error: any) {
      onError(error.message || 'Streaming failed');
    }
  },

  getHistory: async (contentId: string): Promise<Message[]> => {
    const response = await apiClient.get<Message[]>(
      API_ENDPOINTS.CHAT.HISTORY(contentId)
    );
    return response.data;
  },
};

