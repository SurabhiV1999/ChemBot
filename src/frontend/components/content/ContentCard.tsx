import React from 'react';
import { Content } from '../../utils/types';
import { formatDate, formatFileSize } from '../../utils/validators';

interface ContentCardProps {
  content: Content;
  onSelect: (content: Content) => void;
  onDelete: (id: string) => void;
  isSelected?: boolean;
}

const ContentCard: React.FC<ContentCardProps> = ({ 
  content, 
  onSelect, 
  onDelete,
  isSelected = false 
}) => {
  const statusColors = {
    processing: 'bg-yellow-100 text-yellow-800',
    ready: 'bg-green-100 text-green-800',
    error: 'bg-red-100 text-red-800',
  };

  const statusLabels = {
    processing: 'Processing',
    ready: 'Ready',
    error: 'Error',
  };

  return (
    <div
      className={`
        bg-white rounded-lg border-2 p-4 cursor-pointer transition-all hover:shadow-md
        ${isSelected ? 'border-primary-500 shadow-md' : 'border-gray-200'}
      `}
      onClick={() => onSelect(content)}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-semibold text-gray-900 truncate">
            {content.title}
          </h3>
          <p className="text-sm text-gray-600 mt-1 truncate">
            {content.fileName}
          </p>
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span>{formatFileSize(content.fileSize)}</span>
            <span>•</span>
            <span>{formatDate(content.uploadedAt)}</span>
          </div>
        </div>

        <div className="flex items-start gap-2 ml-3">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[content.status]}`}>
            {statusLabels[content.status]}
          </span>
          
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (window.confirm('Are you sure you want to delete this content?')) {
                onDelete(content.id);
              }
            }}
            className="text-gray-400 hover:text-red-600 transition-colors"
            title="Delete"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ContentCard;

