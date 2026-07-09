import api from './api';
import type { CompositionConstraints, CompositionResult, CompositionTask, PaperTemplate } from '../types/composition';

export const compositionService = {
  generate: (constraints: CompositionConstraints) =>
    api.post<{ task_id: string; message: string }>('/composition/generate', constraints),

  getTask: (taskId: string) =>
    api.get<CompositionTask>(`/composition/task/${taskId}`),

  getById: (id: number) =>
    api.get<CompositionResult>(`/composition/${id}`),

  adjust: (compositionId: number, changes: Record<string, unknown>[]) =>
    api.post('/composition/adjust', { composition_id: compositionId, changes }),

  exportPdf: (id: number) =>
    api.post(`/composition/${id}/export?format=pdf`, {}, { responseType: 'blob' }),

  exportWord: (id: number) =>
    api.post(`/composition/${id}/export?format=word`, {}, { responseType: 'blob' }),

  saveTemplate: (name: string, constraints: CompositionConstraints) =>
    api.post<{ id: number; message: string }>('/composition/templates', { name, constraints }),

  listTemplates: () =>
    api.get<PaperTemplate[]>('/composition/templates'),

  getAlternatives: (questionId: number, n: number = 3) =>
    api.get<{ question_id: number; alternatives: number[] }>(`/composition/alternatives/${questionId}`, { params: { n } }),
};
