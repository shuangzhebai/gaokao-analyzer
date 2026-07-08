export const SUBJECTS: Record<string, string> = {
  chinese: '语文', math: '数学', english: '英语',
  physics: '物理', chemistry: '化学', biology: '生物',
  history: '历史', geography: '地理', politics: '政治',
};

export const PAPER_TYPES = [
  { value: '月考', label: '月考' },
  { value: '期中', label: '期中' },
  { value: '期末', label: '期末' },
  { value: '一模', label: '一模' },
  { value: '二模', label: '二模' },
  { value: '三模', label: '三模' },
  { value: '高考真题', label: '高考真题' },
  { value: '模拟卷', label: '模拟卷' },
  { value: '联考', label: '联考' },
];

export const ANALYSIS_STATUS_MAP: Record<string, string> = {
  pending: '待处理', parsed: '已解析',
  analyzing: '分析中', irt_estimated: '已IRT',
  simulated: '已模拟', analyzed: '已完成', failed: '失败',
};
