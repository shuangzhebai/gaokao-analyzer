import api from './api';
import type {
  CollectionStats,
  CollectionTargetProgress,
  CollectionTriggerResponse,
  CollectionLogsResponse,
} from '../types/collection';

/** 开始采集 */
export async function startCollect(params: {
  source?: string;
  year?: number;
}): Promise<unknown> {
  const res = await api.post('/collect', params);
  return res.data;
}

/** 获取采集状态 */
export async function getCollectStatus(): Promise<unknown> {
  const res = await api.get('/collect/status');
  return res.data;
}

/** 获取采集统计（总题数 / 各来源 / 各学科 / 趋势） */
export async function getCollectionStats(): Promise<CollectionStats> {
  const res = await api.get('/collection/stats');
  return res.data;
}

/** 手动触发采集任务 */
export async function triggerCollection(): Promise<CollectionTriggerResponse> {
  const res = await api.post('/collection/trigger');
  return res.data;
}

/** 获取目标进度 */
export async function getCollectionTarget(): Promise<CollectionTargetProgress> {
  const res = await api.get('/collection/target');
  return res.data;
}

/** 获取采集日志列表 */
export async function getCollectionLogs(
  limit = 50,
  offset = 0
): Promise<CollectionLogsResponse> {
  const res = await api.get('/collection/logs', {
    params: { limit, offset },
  });
  return res.data;
}
