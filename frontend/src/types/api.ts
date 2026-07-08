import type { Paper, PaginatedResponse, DashboardStats, FilterMeta, SearchSuggestion } from './index';

export interface PapersListParams {
  q?: string;
  subject?: string;
  paper_type?: string;
  year?: number;
  province?: string;
  analysis_status?: string;
  page?: number;
  size?: number;
}

export interface UploadPaperParams {
  file: File;
  title: string;
  subject: string;
  paper_type: string;
  year: number;
  province: string;
}

export interface SearchParams {
  q: string;
  subject?: string;
  sort?: string;
  page?: number;
  size?: number;
}

export interface ApiError {
  detail: string;
  status?: number;
}

export type { Paper, PaginatedResponse, DashboardStats, FilterMeta, SearchSuggestion };
