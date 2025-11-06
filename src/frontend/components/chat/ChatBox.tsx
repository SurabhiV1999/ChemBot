import React, { useEffect, useRef } from 'react';
import { useChat } from '../../context/ChatContext';
import { useContent } from '../../context/ContentContext';
import Message from './Message';
import InputBox from './InputBox';
import Loader from '../shared/Loader';
import ErrorMessage from '../shared/ErrorMessage';

const ChatBox: React.FC = () => {
  const { messages, isLoading, isStreaming, streamingMessage, error, askQuestion, loadHistory, clearMessages } = useChat();
  const { selectedContent } = useContent();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive or streaming
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  // Clear messages when content changes (start fresh every time)
  useEffect(() => {
    if (selectedContent) {
      clearMessages(); // Start with a fresh, empty chat screen
    }
  }, [selectedContent?.id]);

  const handleSendQuestion = async (question: string) => {
    if (!selectedContent) return;

    try {
      await askQuestion({
        contentId: selectedContent.id,
        question,
      });
    } catch (err) {
      console.error('Failed to send question:', err);
    }
  };

  if (!selectedContent) {
    return (
      <div className="bg-white rounded-xl shadow-lg h-full flex flex-col">
        <div className="flex-1 flex items-center justify-center p-12">
          <div className="text-center max-w-md">
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
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              No content selected
            </h3>
            <p className="text-gray-600">
              Select a content from your list to start asking questions
            </p>
          </div>
        </div>
        <InputBox onSend={handleSendQuestion} isLoading={false} disabled={true} />
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-lg h-full flex flex-col">
      {/* Header */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold text-gray-900 truncate">
                {selectedContent.title}
              </h2>
              <p className="text-sm text-gray-600">
                Ask me anything about this content
              </p>
            </div>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => {
                if (window.confirm('Are you sure you want to end this conversation? All messages will be cleared.')) {
                  clearMessages();
                }
              }}
              className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 focus:outline-none focus:ring-2 focus:ring-red-500 transition-colors"
              title="End conversation and start fresh"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              End Conversation
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex justify-start">
            <div className="max-w-3xl">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="bg-gray-100 rounded-lg px-4 py-3 shadow">
                    <p className="text-sm text-gray-900">
                      👋 Hello! I'm ChemBot, your AI learning assistant. I've analyzed your uploaded material and I'm ready to help you understand it better. What would you like to learn about?
                    </p>
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Just now
                  </p>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <Message key={message.id} message={message} />
            ))}
          </>
        )}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-3">
              <Loader size="sm" message="Thinking..." />
            </div>
          </div>
        )}

        {isStreaming && (
          <div className="flex justify-start">
            <div className="max-w-3xl">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="bg-gray-100 rounded-lg px-4 py-3 shadow">
                    {streamingMessage ? (
                      <>
                        <p className="text-sm text-gray-900 whitespace-pre-wrap">{streamingMessage}</p>
                        {/* Typing indicator */}
                        <div className="flex items-center gap-1 mt-2">
                          <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse"></span>
                          <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></span>
                          <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></span>
                        </div>
                      </>
                    ) : (
                      <div className="flex items-center gap-2">
                        <svg className="w-5 h-5 animate-spin text-primary-600" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span className="text-sm text-gray-600">Thinking...</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Old streaming display - keeping for backwards compat but this is now redundant */}
        {false && isStreaming && streamingMessage && (
          <div className="flex justify-start">
            <div className="max-w-3xl">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <div className="bg-gray-100 rounded-lg px-4 py-3 shadow">
                    <p className="text-sm text-gray-900 whitespace-pre-wrap">{streamingMessage}</p>
                    {/* Typing indicator */}
                    <div className="flex items-center gap-1 mt-2">
                      <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse"></span>
                      <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" style={{animationDelay: '0.2s'}}></span>
                      <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse" style={{animationDelay: '0.4s'}}></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {error && (
          <ErrorMessage message={error} />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <InputBox 
        onSend={handleSendQuestion} 
        isLoading={isLoading || isStreaming}
        disabled={selectedContent.status !== 'ready'}
        placeholder={
          selectedContent.status === 'processing' 
            ? 'Content is being processed. Please wait...' 
            : 'Ask a question about the content...'
        }
      />
    </div>
  );
};

export default ChatBox;

