import api from './api';
import type { DashboardStats } from '../types';

export async function getDashboard(): Promise<DashboardStats> {
  const res = await api.get('/papers/dashboard');
  return res.data;
}
