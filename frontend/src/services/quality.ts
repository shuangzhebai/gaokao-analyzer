import api from './api';
import type { QualityReport, CompareResult } from '../types/quality';

export const qualityService = {
  analyze: (questionIds: number[]) =>
    api.post<QualityReport[]>('/quality/analyze', { question_ids: questionIds }),

  batch: (paperIds: number[]) =>
    api.post('/quality/batch', { paper_ids: paperIds }),

  getReport: (id: number) =>
    api.get<QualityReport>(`/quality/report/${id}`),

  compare: (paperIds: number[]) =>
    api.get<CompareResult[]>('/quality/compare', { params: { paper_ids: paperIds.join(',') } }),

  precompute: () =>
    api.post('/quality/precompute'),
};
