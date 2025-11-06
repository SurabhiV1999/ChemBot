import React, { useEffect } from 'react';
import { useContent } from '../../context/ContentContext';
import ContentCard from './ContentCard';
import Loader from '../shared/Loader';
import ErrorMessage from '../shared/ErrorMessage';

const ContentList: React.FC = () => {
  const { 
    contents, 
    selectedContent, 
    isLoading, 
    error, 
    fetchContents, 
    selectContent,
    deleteContent 
  } = useContent();

  useEffect(() => {
    fetchContents();
  }, []);

  if (isLoading && contents.length === 0) {
    return (
      <div className="flex justify-center py-12">
        <Loader message="Loading your content..." />
      </div>
    );
  }

  if (error && contents.length === 0) {
    return <ErrorMessage message={error} onRetry={fetchContents} />;
  }

  if (contents.length === 0) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-12 text-center">
        <svg
          className="w-16 h-16 text-gray-400 mx-auto mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h3 className="text-xl font-semibold text-gray-900 mb-2">
          No content yet
        </h3>
        <p className="text-gray-600">
          Upload your first document to get started with ChemBot!
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">My Content</h2>
      <div className="space-y-3">
        {contents.map((content) => (
          <ContentCard
            key={content.id}
            content={content}
            onSelect={selectContent}
            onDelete={deleteContent}
            isSelected={selectedContent?.id === content.id}
          />
        ))}
      </div>
    </div>
  );
};

export default ContentList;

