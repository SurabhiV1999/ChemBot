import React from 'react';
import { Message as MessageType } from '../../utils/types';
import { formatDate } from '../../utils/validators';

interface MessageProps {
  message: MessageType;
}

const Message: React.FC<MessageProps> = ({ message }) => {
  // Don't render answer section if it's just a placeholder
  const hasAnswer = message.answer && message.answer !== '...';
  
  return (
    <div className="space-y-4">
      {/* User Question */}
      <div className="flex justify-end">
        <div className="max-w-3xl">
          <div className="bg-primary-600 text-white rounded-lg px-4 py-3 shadow">
            <p className="text-sm">{message.question}</p>
          </div>
          <p className="text-xs text-gray-500 mt-1 text-right">
            {formatDate(message.timestamp)}
          </p>
        </div>
      </div>

      {/* AI Answer - only show if there's a real answer */}
      {hasAnswer && (
      <div className="flex justify-start">
        <div className="max-w-3xl">
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M10 2a8 8 0 100 16 8 8 0 000-16zm1 11H9v-2h2v2zm0-4H9V5h2v4z" />
              </svg>
            </div>
            <div className="flex-1">
              <div className="bg-gray-100 rounded-lg px-4 py-3 shadow">
                <p className="text-sm text-gray-900 whitespace-pre-wrap">{message.answer}</p>
                {/* Caching and Confidence indicators */}
                {(message.cached || message.confidence_score) && (
                  <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-200">
                    {message.cached && (
                      <div className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span className="font-medium">Instant (Cached)</span>
                      </div>
                    )}
                    {message.confidence_score && (
                      <div className="flex items-center gap-1.5 text-xs text-blue-600">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                        </svg>
                        <span>Confidence: {(message.confidence_score * 100).toFixed(0)}%</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                {formatDate(message.timestamp)}
              </p>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
};

export default Message;

