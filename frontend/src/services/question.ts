import api from './api';
import type { Question, QuestionType, ClassifyResult, QuestionListParams } from '../types/question';

export const questionService = {
  list: (params?: QuestionListParams) =>
    api.get<{ data: Question[]; total: number; page: number; size: number }>('/questions', { params }),

  getById: (id: number) =>
    api.get<Question>(`/questions/${id}`),

  create: (data: Partial<Question>) =>
    api.post<Question>('/questions', data),

  update: (id: number, data: Partial<Question>) =>
    api.put<Question>(`/questions/${id}`, data),

  delete: (id: number) =>
    api.delete(`/questions/${id}`),

  classify: (questions: Partial<Question>[]) =>
    api.post<ClassifyResult[]>('/questions/classify', { questions }),

  getTypes: () =>
    api.get<QuestionType[]>('/questions/types'),

  getQuality: (id: number) =>
    api.get(`/questions/${id}/quality`),
};
