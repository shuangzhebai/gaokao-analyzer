import { useEffect, useRef } from 'react';
import * as echarts from 'echarts/core';
import { Box } from '@mui/material';

export default function ChartView({ option, height = 300 }: { option: Record<string, unknown>; height?: number }) {
  const chartRef = useRef<HTMLDivElement>(null);
  const instanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!instanceRef.current) {
      instanceRef.current = echarts.init(chartRef.current, undefined, { renderer: 'canvas' });
    }
    instanceRef.current.setOption(option, true);
    const handleResize = () => instanceRef.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      instanceRef.current?.dispose();
      instanceRef.current = null;
    };
  }, [option]);

  return <Box ref={chartRef} sx={{ width: '100%', height }} />;
}
