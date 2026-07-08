// 基础类型
export interface Paper {
  id: number;
  title: string;
  subject: string;
  subject_name: string;
  paper_type: string;
  year: number;
  province: string;
  school: string;
  exam_tag: string;
  source_url: string;
  tags: string;
  analysis_status: string;
  total_score: number;
  question_count: number;
  created_at: string;
}

export interface Question {
  id: number;
  paper_id: number;
  index: number;
  type: string;
  score: number;
  content: string;
  answer: string;
  analysis: string;
  difficulty: number;
  discrimination: number;
  guessing: number;
  knowledge_points: string;
}

export interface AnalysisResult {
  id: number;
  paper_id: number;
  dimension: string;
  score: number;
  detail: string;
  created_at: string;
}

export interface SimulationResult {
  mean: number;
  std: number;
  median: number;
  min: number;
  max: number;
  q1: number;
  q3: number;
  p90: number;
  p95: number;
  p99: number;
  grade_assignment: Record<string, unknown>;
  segment_rates: unknown[];
}

export interface DashboardStats {
  total_papers: number;
  total_questions: number;
  analyzed_count: number;
  subject_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  recent_papers: Paper[];
  auto_scraper_status: unknown;
}

export interface User {
  id: number;
  username: string;
  email?: string;
  role: string;
  tenant_id?: string;
}

export interface LoginResponse {
  token: string;
  token_type: string;
  user: User;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  size: number;
  data: T[];
  query?: string;
}

export interface FilterMeta {
  subjects: { id: string; name: string }[];
  paper_types: { value: string; label: string }[];
  provinces: string[];
  exam_tags: string[];
  analysis_statuses: string[];
}

export interface SearchSuggestion {
  id: number;
  title: string;
  subject_name: string;
  year: number;
}
