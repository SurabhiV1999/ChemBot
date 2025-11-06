import React, { useState, useRef } from 'react';
import { useContent } from '../../context/ContentContext';
import { validateFile } from '../../utils/validators';
import Loader from '../shared/Loader';
import ErrorMessage from '../shared/ErrorMessage';

interface FileUploadProps {
  onUploadSuccess?: () => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const { uploadContent, isLoading } = useContent();
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelection(files[0]);
    }
  };

  const handleFileSelection = (file: File) => {
    const validation = validateFile(file);
    if (!validation.valid) {
      setError(validation.message || 'Invalid file');
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setError(null);
    
    // Auto-populate title from filename
    if (!title) {
      const fileNameWithoutExtension = file.name.replace(/\.[^/.]+$/, '');
      setTitle(fileNameWithoutExtension);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelection(files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedFile) {
      setError('Please select a file');
      return;
    }

    if (!title.trim()) {
      setError('Please enter a title');
      return;
    }

    try {
      await uploadContent(selectedFile, title);
      
      // Reset form
      setSelectedFile(null);
      setTitle('');
      setError(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      onUploadSuccess?.();
    } catch (err: any) {
      setError(err.message || 'Upload failed');
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Upload Content</h2>

      {error && (
        <div className="mb-4">
          <ErrorMessage message={error} onRetry={() => setError(null)} />
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Drag and Drop Area */}
        <div
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all
            ${isDragging 
              ? 'border-primary-500 bg-primary-50' 
              : 'border-gray-300 hover:border-primary-400 hover:bg-gray-50'
            }
            ${selectedFile ? 'bg-green-50 border-green-300' : ''}
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileInputChange}
            accept=".pdf,.txt,.docx,.md"
            className="hidden"
            disabled={isLoading}
          />

          <div className="flex flex-col items-center gap-3">
            <svg
              className={`w-12 h-12 ${selectedFile ? 'text-green-500' : 'text-gray-400'}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>

            {selectedFile ? (
              <div>
                <p className="text-green-700 font-medium">{selectedFile.name}</p>
                <p className="text-gray-600 text-sm mt-1">
                  {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                </p>
                <p className="text-gray-500 text-xs mt-2">Click to change file</p>
              </div>
            ) : (
              <div>
                <p className="text-gray-700 font-medium">
                  Drag and drop your file here
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  or click to browse
                </p>
                <p className="text-gray-400 text-xs mt-2">
                  Supported: PDF, TXT, DOCX, MD (Max 10MB)
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Title Input */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
            Content Title
          </label>
          <input
            type="text"
            id="title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Enter a title for this content"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={isLoading}
          />
        </div>

        {/* Upload Button */}
        <button
          type="submit"
          disabled={isLoading || !selectedFile}
          className="w-full bg-primary-600 text-white py-3 rounded-lg font-medium
            hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
            disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {isLoading ? (
            <div className="flex items-center justify-center gap-2">
              <Loader size="sm" />
              <span>Uploading...</span>
            </div>
          ) : (
            'Upload Content'
          )}
        </button>
      </form>
    </div>
  );
};

export default FileUpload;

