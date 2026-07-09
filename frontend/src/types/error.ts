export interface ErrorRecord {
  id: number;
  user_id: number;
  question_id: number;
  subject_id: string;
  error_reason: 'concept' | 'careless' | 'calculation' | 'strategy' | 'other';
  user_score?: number;
  question_score: number;
  attempt_count: number;
  is_mastered: boolean;
  mastered_at?: string;
  created_at: string;
}

export interface WeaknessDiagnosis {
  theta: number;
  weakness_top5: { knowledge_point: string; mastery: number }[];
  suggestions: string[];
}

export interface ErrorStats {
  total_errors: number;
  by_subject: Record<string, number>;
  by_reason: Record<string, number>;
  trend: { date: string; count: number }[];
}
