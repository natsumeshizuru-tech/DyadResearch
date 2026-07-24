import ReactECharts from "echarts-for-react";
import { dateLabel } from "../lib/format.js";

const COLORS = {
  cyan: "#21c7bd",
  cyanSoft: "rgba(33, 199, 189, 0.16)",
  blue: "#5a8cff",
  orange: "#f59e5b",
  red: "#ef5b5b",
  green: "#42c98d",
  grid: "#273343",
  axis: "#6e7b8b",
  text: "#aeb9c7",
};

const base = {
  animationDuration: 260,
  textStyle: { color: COLORS.text, fontFamily: "Inter, Segoe UI, Microsoft YaHei, sans-serif" },
  tooltip: {
    trigger: "axis",
    backgroundColor: "#17212d",
    borderColor: "#344255",
    textStyle: { color: "#e7edf5", fontSize: 11 },
  },
  grid: { left: 48, right: 18, top: 30, bottom: 38, containLabel: false },
  xAxis: {
    type: "category",
    axisLine: { lineStyle: { color: COLORS.grid } },
    axisTick: { show: false },
    axisLabel: { color: COLORS.axis, fontSize: 10, hideOverlap: true },
  },
  yAxis: {
    type: "value",
    scale: true,
    splitLine: { lineStyle: { color: COLORS.grid, opacity: 0.8 } },
    axisLabel: { color: COLORS.axis, fontSize: 10 },
  },
};

export function EquityChart({ equity = [], benchmark = [] }) {
  const labels = equity.map((point) => timestampLabel(point.ts));
  const values = equity.map((point) => Number(point.net_value));
  const benchmarkValues = benchmark.map((point) => Number(point.net_value));
  const option = {
    ...base,
    legend: {
      data: ["策略净值", "基准(沪深300)"],
      top: 2,
      left: 12,
      itemWidth: 14,
      textStyle: { color: COLORS.text, fontSize: 10 },
    },
    xAxis: { ...base.xAxis, data: labels },
    yAxis: { ...base.yAxis, axisLabel: { ...base.yAxis.axisLabel, formatter: (value) => value.toFixed(2) } },
    series: [
      {
        name: "策略净值",
        type: "line",
        data: values,
        showSymbol: false,
        smooth: 0.14,
        lineStyle: { color: COLORS.cyan, width: 1.8 },
        itemStyle: { color: COLORS.cyan },
        areaStyle: { color: COLORS.cyanSoft },
      },
      {
        name: "基准(沪深300)",
        type: "line",
        data: benchmarkValues,
        showSymbol: false,
        lineStyle: { color: COLORS.text, width: 1.1, type: "dashed" },
        itemStyle: { color: COLORS.text },
      },
    ],
  };
  return <ReactECharts option={option} notMerge className="chart" opts={{ renderer: "svg" }} />;
}

export function DrawdownChart({ equity = [] }) {
  const option = {
    ...base,
    grid: { left: 48, right: 18, top: 12, bottom: 30 },
    xAxis: { ...base.xAxis, data: equity.map((point) => timestampLabel(point.ts)), axisLabel: { show: false } },
    yAxis: {
      ...base.yAxis,
      max: 0,
      axisLabel: { ...base.yAxis.axisLabel, formatter: (value) => `${(value * 100).toFixed(0)}%` },
    },
    series: [{
      type: "line",
      data: equity.map((point) => Number(point.drawdown)),
      showSymbol: false,
      lineStyle: { color: COLORS.red, width: 1.2 },
      areaStyle: { color: "rgba(239, 91, 91, 0.18)" },
    }],
  };
  return <ReactECharts option={option} notMerge className="chart chart-short" opts={{ renderer: "svg" }} />;
}

export function MarketChart({ bars = [] }) {
  const labels = bars.map(barLabel);
  const option = {
    ...base,
    legend: { show: false },
    grid: [
      { left: 48, right: 18, top: 18, height: "64%" },
      { left: 48, right: 18, top: "72%", height: "17%" },
    ],
    xAxis: [
      { ...base.xAxis, data: labels, gridIndex: 0, axisLabel: { show: false } },
      { ...base.xAxis, data: labels, gridIndex: 1 },
    ],
    yAxis: [
      { ...base.yAxis, gridIndex: 0, splitNumber: 5 },
      {
        ...base.yAxis,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: {
          ...base.yAxis.axisLabel,
          formatter: (value) => `${Math.round(value / 10000)}万`,
        },
      },
    ],
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: [0, 1],
        start: Math.max(0, 100 - 12000 / Math.max(bars.length, 1)),
        end: 100,
      },
      {
        type: "slider",
        xAxisIndex: [0, 1],
        height: 18,
        bottom: 3,
        borderColor: COLORS.grid,
        fillerColor: "rgba(90, 140, 255, 0.16)",
        backgroundColor: "#141d28",
        textStyle: { color: COLORS.axis },
      },
    ],
    series: [
      {
        name: "价格",
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: bars.map((bar) => [bar.open, bar.close, bar.low, bar.high].map(Number)),
        itemStyle: {
          color: COLORS.red,
          color0: COLORS.green,
          borderColor: COLORS.red,
          borderColor0: COLORS.green,
        },
      },
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: bars.map((bar) => ({
          value: Number(bar.volume),
          itemStyle: { color: Number(bar.close) >= Number(bar.open) ? COLORS.red : COLORS.green },
        })),
        barMaxWidth: 8,
      },
    ],
  };
  return <ReactECharts option={option} notMerge className="chart chart-market" opts={{ renderer: "canvas" }} />;
}

export function FactorSeriesChart({ observations = [] }) {
  const option = {
    ...base,
    legend: {
      data: ["因子值", "20日均值"],
      top: 2,
      left: 10,
      itemWidth: 14,
      textStyle: { color: COLORS.text, fontSize: 10 },
    },
    xAxis: { ...base.xAxis, data: observations.map((item) => dateLabel(item.trade_date)) },
    series: [
      {
        name: "因子值",
        type: "line",
        data: observations.map((item) => Number(item.value)),
        showSymbol: false,
        lineStyle: { color: COLORS.blue, width: 1.4 },
      },
      {
        name: "20日均值",
        type: "line",
        data: rollingMean(observations.map((item) => Number(item.value)), 20),
        showSymbol: false,
        lineStyle: { color: COLORS.orange, width: 1.2 },
      },
    ],
  };
  return <ReactECharts option={option} notMerge className="chart" opts={{ renderer: "svg" }} />;
}

export function DistributionChart({ observations = [] }) {
  const values = observations.map((item) => Number(item.value)).filter(Number.isFinite);
  const bins = histogram(values, 10);
  const option = {
    ...base,
    grid: { left: 48, right: 18, top: 18, bottom: 34 },
    xAxis: { ...base.xAxis, data: bins.map((bin) => bin.label) },
    yAxis: { ...base.yAxis, minInterval: 1 },
    series: [{ type: "bar", data: bins.map((bin) => bin.count), itemStyle: { color: COLORS.blue }, barMaxWidth: 34 }],
  };
  return <ReactECharts option={option} notMerge className="chart" opts={{ renderer: "svg" }} />;
}

function rollingMean(values, window) {
  return values.map((_, index) => {
    const start = Math.max(0, index - window + 1);
    const selected = values.slice(start, index + 1);
    return selected.reduce((sum, value) => sum + value, 0) / selected.length;
  });
}

function histogram(values, count) {
  if (!values.length) return [];
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const width = maximum === minimum ? 1 : (maximum - minimum) / count;
  return Array.from({ length: count }, (_, index) => {
    const lower = minimum + index * width;
    const upper = index === count - 1 ? maximum + Number.EPSILON : lower + width;
    return {
      label: lower.toFixed(2),
      count: values.filter((value) => value >= lower && value < upper).length,
    };
  });
}

function timestampLabel(value) {
  const date = new Date(Number(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toISOString().slice(0, 10);
}

function barLabel(bar) {
  const date = new Date(Number(bar.ts));
  if (Number.isNaN(date.getTime())) return dateLabel(bar.trade_date);
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}`;
}
