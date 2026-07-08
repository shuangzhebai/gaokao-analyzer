import api from './api';

export async function startCollect(params: { source?: string; year?: number }): Promise<unknown> {
  const res = await api.post('/collect', params);
  return res.data;
}

export async function getCollectStatus(): Promise<unknown> {
  const res = await api.get('/collect/status');
  return res.data;
}
