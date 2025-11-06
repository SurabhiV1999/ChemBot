import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ContentProvider } from './context/ContentContext';
import { ChatProvider } from './context/ChatContext';
import ProtectedRoute from './components/auth/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import ContentListPage from './pages/ContentListPage';
import ChatbotPage from './pages/ChatbotPage';
import AnalyticsPage from './pages/AnalyticsPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ContentProvider>
          <ChatProvider>
            <Routes>
              {/* Public Routes */}
              <Route path="/login" element={<LoginPage />} />

              {/* Protected Routes */}
              <Route
                path="/contents"
                element={
                  <ProtectedRoute>
                    <ContentListPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/chat"
                element={
                  <ProtectedRoute>
                    <ChatbotPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/analytics"
                element={
                  <ProtectedRoute>
                    <AnalyticsPage />
                  </ProtectedRoute>
                }
              />

              {/* Default Route */}
              <Route path="/" element={<Navigate to="/contents" replace />} />
              
              {/* 404 Redirect */}
              <Route path="*" element={<Navigate to="/contents" replace />} />
            </Routes>
          </ChatProvider>
        </ContentProvider>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;

