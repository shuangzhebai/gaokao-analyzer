import api from './api';
import type { Paper, PaginatedResponse } from '../types';
import type { PapersListParams, UploadPaperParams, SearchParams } from '../types/api';

export async function listPapers(params: PapersListParams): Promise<PaginatedResponse<Paper>> {
  const res = await api.get('/papers', { params });
  return res.data;
}

export async function getPaper(id: number): Promise<Paper> {
  const res = await api.get(`/papers/${id}`);
  return res.data;
}

export async function deletePaper(id: number): Promise<void> {
  await api.delete(`/papers/${id}`);
}

export async function uploadPaper(params: UploadPaperParams): Promise<Paper> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('title', params.title);
  formData.append('subject', params.subject);
  formData.append('paper_type', params.paper_type);
  formData.append('year', String(params.year));
  formData.append('province', params.province);
  const res = await api.post('/papers/upload', formData);
  return res.data;
}

export async function estimateIrt(paperId: number, nStudents = 50000): Promise<{ task_id: string }> {
  const res = await api.post(`/papers/${paperId}/simulate`, { n_students: nStudents });
  return res.data;
}

export async function simulateBatch(params: { n_students?: number; subject?: string }): Promise<{ task_id: string }> {
  const res = await api.post('/papers/batch/simulate', params);
  return res.data;
}

export async function getTaskStatus(taskId: string): Promise<unknown> {
  const res = await api.get(`/tasks/${taskId}`);
  return res.data;
}

export async function searchPapers(params: SearchParams): Promise<PaginatedResponse<Paper>> {
  const res = await api.get('/search', { params });
  return res.data;
}
