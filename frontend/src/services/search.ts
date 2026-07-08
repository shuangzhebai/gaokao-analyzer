import api from './api';
import type { SearchSuggestion } from '../types';

export async function getSuggestions(q: string): Promise<SearchSuggestion[]> {
  const res = await api.get('/search/suggest', { params: { q } });
  return res.data;
}
