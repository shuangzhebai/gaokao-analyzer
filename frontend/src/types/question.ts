export interface QuestionType {
  id: number;
  subject_id: string;
  main_type: string;
  sub_type: string;
  name_cn: string;
  level: number;
  parent_id?: number;
  children?: QuestionType[];
}

export interface Question {
  id: number;
  paper_id?: number;
  question_type_id?: number;
  question_type?: QuestionType;
  q_number: number;
  q_type: string;
  content: string;
  options?: string;
  answer?: string;
  explanation?: string;
  score: number;
  knowledge_points: string;
  difficulty_tag?: string;
  irt_a?: number;
  irt_b?: number;
  irt_c?: number;
  source?: string;
  year?: number;
  created_at: string;
}

export interface ClassifyResult {
  main_type: string;
  sub_type: string;
  confidence: number;
}

export interface QuestionListParams {
  subject_id?: string;
  question_type_id?: number;
  source?: string;
  year?: number;
  page?: number;
  size?: number;
}
