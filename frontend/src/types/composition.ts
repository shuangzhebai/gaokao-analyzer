export interface CompositionConstraints {
  subject_id: string;
  total_count: number;
  total_score?: number;
  difficulty_mean: number;
  difficulty_std: number;
  types: { id: number; name: string; count: number; score: number }[];
  knowledge_points: { code: string; name: string; weight: number }[];
  prefer_real_exam: boolean;
}

export interface CompositionResult {
  id: number;
  name: string;
  question_ids: number[];
  total_score: number;
  constraints_satisfied: boolean;
  objective_score: number;
  quality_report?: {
    difficulty_distribution: Record<string, number>;
    knowledge_coverage: number;
    reliability_estimate: number;
    warnings: string[];
  };
  export_url?: string;
}

export interface PaperTemplate {
  id: number;
  name: string;
  subject_id: string;
  constraints_json: string;
  is_public: boolean;
  created_at: string;
}

export interface CompositionTask {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  result?: CompositionResult;
  error?: string;
}
