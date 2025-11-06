import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { validateEmail, validatePassword } from '../../utils/validators';
import { authApi } from '../../api/auth';
import Loader from '../shared/Loader';
import ErrorMessage from '../shared/ErrorMessage';

const LoginForm: React.FC = () => {
  const navigate = useNavigate();
  const { login, isLoading: authLoading } = useAuth();
  
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState<'student' | 'teacher'>('student');
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; name?: string; general?: string }>({});

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate inputs
    const newErrors: { email?: string; password?: string; name?: string } = {};
    
    if (!email) {
      newErrors.email = 'Email is required';
    } else if (!validateEmail(email)) {
      newErrors.email = 'Please enter a valid email';
    }
    
    if (!password) {
      newErrors.password = 'Password is required';
    } else {
      const passwordValidation = validatePassword(password);
      if (!passwordValidation.valid) {
        newErrors.password = passwordValidation.message;
      }
    }
    
    if (isRegister && !name) {
      newErrors.name = 'Name is required';
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }
    
    setIsLoading(true);
    
    try {
      if (isRegister) {
        // Register new user
        await authApi.register({ email, password, name, role });
        // Then login
        await login({ email, password });
      } else {
        // Just login
        await login({ email, password });
      }
      navigate('/contents');
    } catch (err: any) {
      setErrors({ general: err.response?.data?.detail || err.message || (isRegister ? 'Registration failed' : 'Login failed') });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <div className="bg-white rounded-xl shadow-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">ChemBot</h1>
          <p className="text-gray-600">Your Educational AI Assistant</p>
        </div>

        {/* Toggle between Login and Register */}
        <div className="flex mb-6 bg-gray-100 p-1 rounded-lg">
          <button
            type="button"
            onClick={() => {
              setIsRegister(false);
              setErrors({});
            }}
            className={`flex-1 py-2 px-4 rounded-md font-medium transition-colors ${
              !isRegister
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => {
              setIsRegister(true);
              setErrors({});
            }}
            className={`flex-1 py-2 px-4 rounded-md font-medium transition-colors ${
              isRegister
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            Register
          </button>
        </div>

        {errors.general && (
          <div className="mb-4">
            <ErrorMessage message={errors.general} />
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          {isRegister && (
            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                Full Name
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => {
                  setName(e.target.value);
                  setErrors(prev => ({ ...prev, name: undefined }));
                }}
                className={`
                  w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                  ${errors.name ? 'border-red-500' : 'border-gray-300'}
                `}
                placeholder="John Doe"
                disabled={isLoading || authLoading}
              />
              {errors.name && (
                <p className="text-red-500 text-sm mt-1">{errors.name}</p>
              )}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setErrors(prev => ({ ...prev, email: undefined }));
              }}
              className={`
                w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                ${errors.email ? 'border-red-500' : 'border-gray-300'}
              `}
              placeholder="you@example.com"
              disabled={isLoading || authLoading}
            />
            {errors.email && (
              <p className="text-red-500 text-sm mt-1">{errors.email}</p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
              Password
            </label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                setErrors(prev => ({ ...prev, password: undefined }));
              }}
              className={`
                w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent
                ${errors.password ? 'border-red-500' : 'border-gray-300'}
              `}
              placeholder="Enter your password"
              disabled={isLoading || authLoading}
            />
            {errors.password && (
              <p className="text-red-500 text-sm mt-1">{errors.password}</p>
            )}
          </div>

          {isRegister && (
            <div>
              <label htmlFor="role" className="block text-sm font-medium text-gray-700 mb-1">
                Role
              </label>
              <select
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value as 'student' | 'teacher')}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                disabled={isLoading || authLoading}
              >
                <option value="student">Student</option>
                <option value="teacher">Teacher</option>
              </select>
            </div>
          )}

          <button
            type="submit"
            disabled={isLoading || authLoading}
            className="w-full bg-primary-600 text-white py-3 rounded-lg font-medium
              hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2
              disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {(isLoading || authLoading) ? (
              <div className="flex items-center justify-center gap-2">
                <Loader size="sm" />
                <span>{isRegister ? 'Creating account...' : 'Signing in...'}</span>
              </div>
            ) : (
              isRegister ? 'Create Account' : 'Sign In'
            )}
          </button>
        </form>

        {!isRegister && (
          <div className="mt-6 text-center text-sm text-gray-600">
            <p>Demo credentials for testing:</p>
            <p className="mt-1 font-mono text-xs">student@example.com / password123</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default LoginForm;

