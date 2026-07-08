import api from './api';
import type { FilterMeta } from '../types';

export async function getFilters(): Promise<FilterMeta> {
  const res = await api.get('/papers/filters');
  return res.data;
}
