/** 采集统计数据类型 */
export interface CollectionStats {
  total_questions: number;
  total_papers: number;
  source_distribution: Record<string, number>;
  subject_distribution: Record<string, number>;
  questions_by_subject: Record<string, number>;
  daily_trend: { date: string; count: number }[];
}

/** 目标进度数据类型 */
export interface CollectionTargetProgress {
  target: {
    mock_papers: number;
    real_exams_years: number;
  };
  collected_mock_papers: number;
  collected_real_exams: number;
  mock_progress_pct: number;
  real_progress_pct: number;
  overall_progress_pct: number;
  year_coverage: Record<string, number>;
}

/** 采集日志记录 */
export interface CollectionLog {
  id: number;
  source: string;
  task_type: string;
  started_at: string;
  completed_at: string | null;
  papers_found: number;
  papers_new: number;
  questions_new: number;
  errors: string[];
  status: string;
}

/** 采集触发响应 */
export interface CollectionTriggerResponse {
  triggered: boolean;
  message?: string;
  error?: string;
}

/** 采集日志列表响应 */
export interface CollectionLogsResponse {
  data: CollectionLog[];
  total: number;
  limit: number;
  offset: number;
}
