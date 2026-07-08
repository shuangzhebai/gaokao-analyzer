import api from './api';

export async function runAudit(paperId: number): Promise<unknown> {
  const res = await api.post(`/audit/${paperId}`);
  return res.data;
}

export async function getAuditResults(params?: Record<string, unknown>): Promise<unknown> {
  const res = await api.get('/audit', { params });
  return res.data;
}
