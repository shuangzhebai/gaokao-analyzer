import api from './api';
import type { LoginResponse, User } from '../types';

export async function login(username: string, password: string): Promise<LoginResponse> {
  const formData = new URLSearchParams({ username, password });
  const res = await api.post('/auth/login', formData.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return res.data;
}

export async function register(username: string, password: string, role = 'viewer'): Promise<User> {
  const formData = new URLSearchParams({ username, password, role });
  const res = await api.post('/auth/register', formData.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return res.data;
}
