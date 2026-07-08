import api from './api';

export async function listDocs(params?: Record<string, unknown>): Promise<unknown> {
  const res = await api.get('/official-docs', { params });
  return res.data;
}
