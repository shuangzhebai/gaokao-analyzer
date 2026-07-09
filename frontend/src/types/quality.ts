export interface QualityReport {
  question_id: number;
  dimensions: {
    difficulty: number;
    discrimination: number;
    reliability: number;
    validity: number;
    knowledge_coverage: number;
    type_match: number;
  };
  ctt_indicators: Record<string, number>;
  irt_parameters: { a?: number; b?: number; c?: number };
  overall_score: number;
}

export interface CompareResult {
  paper_id: number;
  title: string;
  quality_score: number;
  dimensions: QualityReport['dimensions'];
}
