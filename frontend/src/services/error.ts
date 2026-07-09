import api from './api';
import type { ErrorRecord, ErrorStats, WeaknessDiagnosis } from '../types/error';

export const errorService = {
  list: (params: { user_id: number; subject_id?: string; error_reason?: string; is_mastered?: number; page?: number; size?: number }) =>
    api.get<{ data: ErrorRecord[]; total: number; page: number; size: number }>('/errors', { params }),

  record: (data: { user_id: number; question_id: number; subject_id: string; error_reason?: string; user_score?: number; question_score?: number }) =>
    api.post<{ id: number; status: string; attempt_count?: number }>('/errors', data),

  update: (id: number, data: Record<string, unknown>) =>
    api.put(`/errors/${id}`, data),

  delete: (id: number) =>
    api.delete(`/errors/${id}`),

  getStats: (userId: number, subjectId?: string) =>
    api.get<ErrorStats>('/errors/stats', { params: { user_id: userId, subject_id: subjectId } }),

  getDiagnosis: (userId: number, subjectId: string) =>
    api.get<WeaknessDiagnosis>('/errors/diagnosis', { params: { user_id: userId, subject_id: subjectId } }),

  recommend: (questionId: number, n?: number) =>
    api.get(`/errors/recommend/${questionId}`, { params: { n } }),
};
