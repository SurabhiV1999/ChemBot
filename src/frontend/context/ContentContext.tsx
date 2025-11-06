import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { Content, ApiError } from '../utils/types';
import { contentApi } from '../api/content';
import { MESSAGES } from '../utils/constants';

interface ContentContextType {
  contents: Content[];
  selectedContent: Content | null;
  isLoading: boolean;
  error: string | null;
  uploadContent: (file: File, title: string) => Promise<Content>;
  fetchContents: () => Promise<void>;
  selectContent: (content: Content) => void;
  deleteContent: (id: string) => Promise<void>;
  refreshContents: () => Promise<void>;
}

const ContentContext = createContext<ContentContextType | undefined>(undefined);

interface ContentProviderProps {
  children: ReactNode;
}

export const ContentProvider: React.FC<ContentProviderProps> = ({ children }) => {
  const [contents, setContents] = useState<Content[]>([]);
  const [selectedContent, setSelectedContent] = useState<Content | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const uploadContent = async (file: File, title: string): Promise<Content> => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await contentApi.upload(file, title);
      
      // Add to contents list
      setContents(prev => [response.content, ...prev]);
      
      return response.content;
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || MESSAGES.ERROR.GENERIC);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const fetchContents = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await contentApi.list();
      setContents(data);
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || MESSAGES.ERROR.GENERIC);
    } finally {
      setIsLoading(false);
    }
  };

  const refreshContents = async () => {
    // Silent refresh without loading state
    try {
      const data = await contentApi.list();
      setContents(data);
    } catch (err) {
      console.error('Error refreshing contents:', err);
    }
  };

  // Auto-refresh when there are processing items
  useEffect(() => {
    const hasProcessingContent = contents.some(c => c.status === 'processing');
    
    if (hasProcessingContent) {
      const interval = setInterval(() => {
        refreshContents();
      }, 3000); // Refresh every 3 seconds
      
      return () => clearInterval(interval);
    }
  }, [contents]);

  const selectContent = (content: Content) => {
    setSelectedContent(content);
  };

  const deleteContent = async (id: string) => {
    try {
      setIsLoading(true);
      setError(null);
      await contentApi.delete(id);
      
      // Remove from list
      setContents(prev => prev.filter(c => c.id !== id));
      
      // Clear selection if deleted content was selected
      if (selectedContent?.id === id) {
        setSelectedContent(null);
      }
    } catch (err) {
      const apiError = err as ApiError;
      setError(apiError.message || MESSAGES.ERROR.GENERIC);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ContentContext.Provider
      value={{
        contents,
        selectedContent,
        isLoading,
        error,
        uploadContent,
        fetchContents,
        selectContent,
        deleteContent,
        refreshContents,
      }}
    >
      {children}
    </ContentContext.Provider>
  );
};

export const useContent = (): ContentContextType => {
  const context = useContext(ContentContext);
  if (!context) {
    throw new Error('useContent must be used within ContentProvider');
  }
  return context;
};

