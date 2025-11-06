import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Message, ChatRequest, ApiError } from '../utils/types';
import { chatApi } from '../api/chat';
import { MESSAGES } from '../utils/constants';

interface ChatContextType {
  messages: Message[];
  isLoading: boolean;
  isStreaming: boolean;
  streamingMessage: string;
  error: string | null;
  shouldClearHistory: boolean;
  askQuestion: (request: ChatRequest, useStreaming?: boolean) => Promise<void>;
  loadHistory: (contentId: string) => Promise<void>;
  clearMessages: () => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

interface ChatProviderProps {
  children: ReactNode;
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [shouldClearHistory, setShouldClearHistory] = useState(false);

  const askQuestion = async (request: ChatRequest, useStreaming: boolean = true) => {
    try {
      setError(null);
      
      // Check if we should clear history (after user clicked "End Conversation")
      const clearHistory = shouldClearHistory;
      if (clearHistory) {
        setShouldClearHistory(false); // Reset flag after using it
      }
      
      // Immediately add user's question to messages
      const userQuestion: Message = {
        id: `q_${Date.now()}`,
        contentId: request.contentId,
        question: request.question,
        answer: '...', // Placeholder while waiting for answer
        timestamp: new Date().toISOString(),
        userId: '',
      };
      setMessages(prev => [...prev, userQuestion]);
      
      if (useStreaming) {
        // Streaming mode
        setIsStreaming(true);
        setStreamingMessage('');
        
        await chatApi.askQuestionStream(
          request,
          // onChunk
          (chunk: string) => {
            setStreamingMessage(prev => prev + chunk);
          },
          // onComplete
          (fullAnswer: string) => {
            // Update the last message with the full answer
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                id: `msg_${Date.now()}`,
                answer: fullAnswer,
              };
              return updated;
            });
            setStreamingMessage('');
            setIsStreaming(false);
          },
          // onError
          (errorMsg: string) => {
            setError(errorMsg);
            setIsStreaming(false);
            setStreamingMessage('');
            // Update the last message with error
            setMessages(prev => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                answer: `Error: ${errorMsg}`,
              };
              return updated;
            });
          },
          clearHistory
        );
      } else {
        // Non-streaming mode (fallback)
        setIsLoading(true);
        const response = await chatApi.askQuestion(request, clearHistory);

        // Update the last message with the answer
        setMessages(prev => {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...response.message,
            question: request.question, // Ensure question is set
            cached: response.cached,
            confidence_score: response.confidence_score
          };
          return updated;
        });
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || MESSAGES.ERROR.GENERIC);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const loadHistory = async (contentId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const history = await chatApi.getHistory(contentId);
      setMessages(history);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || MESSAGES.ERROR.GENERIC);
    } finally {
      setIsLoading(false);
    }
  };

  const clearMessages = () => {
    setMessages([]);
    setShouldClearHistory(true); // Signal to clear backend history on next question
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        isLoading,
        isStreaming,
        streamingMessage,
        error,
        shouldClearHistory,
        askQuestion,
        loadHistory,
        clearMessages,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = (): ChatContextType => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within ChatProvider');
  }
  return context;
};

