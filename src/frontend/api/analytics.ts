import apiClient from './client';
import { API_ENDPOINTS } from '../utils/constants';

export interface AnalyticsData {
  total_contents: number;
  total_questions: number;
  avg_questions_per_content: number;
  questions_last_7_days: number;
  questions_last_30_days: number;
  avg_confidence_score?: number;
  helpful_responses_percentage?: number;
  contents_by_status?: Record<string, number>;
  questions_by_rating?: Record<string, number>;
}

export const analyticsApi = {
  getStudentAnalytics: async (userId: string, days: number = 30): Promise<AnalyticsData> => {
    const response = await apiClient.get<AnalyticsData>(
      API_ENDPOINTS.ANALYTICS.STUDENT(userId),
      { params: { days } }
    );
    return response.data;
  },
};

