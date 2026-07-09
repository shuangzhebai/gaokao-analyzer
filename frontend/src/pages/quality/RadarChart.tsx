import { useEffect, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import * as echarts from 'echarts/core';
import { RadarChart as EChartsRadar } from 'echarts/charts';
import {
  TooltipComponent,
  RadarComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([EChartsRadar, TooltipComponent, RadarComponent, CanvasRenderer]);

interface RadarChartProps {
  dimensions: Record<string, number>;
  width?: number | string;
  height?: number;
  title?: string;
  color?: string;
}

const DIMENSION_LABELS: Record<string, string> = {
  difficulty: '难度',
  discrimination: '区分度',
  reliability: '信度',
  validity: '效度',
  knowledge_coverage: '知识点覆盖',
  type_match: '题型匹配',
};

export default function RadarChart({
  dimensions,
  width = '100%',
  height = 300,
  title,
  color = '#00d4ff',
}: RadarChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current);
    }
    const chart = instanceRef.current;

    const indicators = Object.entries(dimensions).map(([key, val]) => ({
      name: DIMENSION_LABELS[key] || key,
      max: 1.0,
      value: val,
    }));

    chart.setOption({
      title: title ? {
        text: title,
        textStyle: { color: '#e0e0e0', fontSize: 14 },
        left: 'center',
      } : undefined,
      tooltip: {
        trigger: 'item',
        backgroundColor: '#1a1a2e',
        borderColor: '#333',
        textStyle: { color: '#e0e0e0' },
      },
      radar: {
        indicator: indicators.map((ind) => ({
          name: ind.name,
          max: 1.0,
        })),
        radius: '60%',
        center: ['50%', '55%'],
        axisName: {
          color: '#999',
          fontSize: 11,
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(0, 212, 255, 0.02)', 'rgba(0, 212, 255, 0.04)'],
          },
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(255,255,255,0.1)',
          },
        },
        axisLine: {
          lineStyle: {
            color: 'rgba(255,255,255,0.15)',
          },
        },
      },
      series: [{
        type: 'radar',
        data: [{
          value: Object.values(dimensions),
          areaStyle: {
            color: `rgba(0, 212, 255, 0.2)`,
          },
          lineStyle: {
            color,
            width: 2,
          },
          itemStyle: {
            color,
          },
        }],
        symbol: 'circle',
        symbolSize: 6,
      }],
    });

    const handleResize = () => chart.resize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [dimensions, title, color]);

  return (
    <Box sx={{ width, height }}>
      <div ref={chartRef} style={{ width: '100%', height }} />
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1, justifyContent: 'center' }}>
        {Object.entries(dimensions).map(([key, val]) => (
          <Box key={key} sx={{ textAlign: 'center', px: 1 }}>
            <Typography sx={{ fontSize: 11, color: '#999' }}>{DIMENSION_LABELS[key] || key}</Typography>
            <Typography sx={{ fontSize: 14, color: '#00d4ff', fontWeight: 600 }}>{(val * 100).toFixed(0)}</Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
}
