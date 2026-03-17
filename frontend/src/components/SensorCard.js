"use client";

import { useEffect, useRef, useMemo } from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import {
  getSensorConfig,
  getStatus,
  getStatusLabel,
  getRangePercent,
  formatValue,
} from "@/lib/sensorConfig";

const STATUS_COLORS = {
  normal: { main: "#10b981", gradient: ["#10b981", "#34d399"] },
  warning: { main: "#f59e0b", gradient: ["#f59e0b", "#fbbf24"] },
  danger: { main: "#ef4444", gradient: ["#ef4444", "#f87171"] },
  none: { main: "#64748b", gradient: ["#64748b", "#94a3b8"] },
};

function MiniSparkline({ data, sensorKey, status }) {
  const colors = STATUS_COLORS[status] || STATUS_COLORS.none;
  const gradientId = `gradient-${sensorKey}`;

  if (!data || data.length < 2) {
    return (
      <div className="sparkline-placeholder">
        <div className="sparkline-empty-text">Đang thu thập dữ liệu...</div>
      </div>
    );
  }

  return (
    <div className="sparkline-container">
      <ResponsiveContainer width="100%" height={70}>
        <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors.main} stopOpacity={0.35} />
              <stop offset="100%" stopColor={colors.main} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <YAxis domain={["auto", "auto"]} hide />
          <Tooltip
            contentStyle={{
              background: "rgba(17, 24, 39, 0.95)",
              border: `1px solid ${colors.main}40`,
              borderRadius: "8px",
              padding: "6px 10px",
              fontSize: "12px",
              color: "#f1f5f9",
              boxShadow: `0 4px 12px ${colors.main}20`,
            }}
            labelStyle={{ color: "#94a3b8", fontSize: "10px" }}
            formatter={(val) => [formatValue(val), ""]}
            labelFormatter={(label) => label}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={colors.main}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{ r: 3, fill: colors.main, stroke: "#0a0e1a", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function SensorCard({ sensorKey, value, previousValue, history }) {
  const cardRef = useRef(null);
  const config = getSensorConfig(sensorKey);

  if (!config) return null;

  const status = getStatus(sensorKey, value);
  const statusLabel = getStatusLabel(status);
  const rangePercent = getRangePercent(sensorKey, value);
  const displayValue = formatValue(value);
  const hasData = value !== null && value !== undefined;

  // Prepare chart data from history
  const chartData = useMemo(() => {
    if (!history || history.length === 0) return [];
    return history
      .filter((entry) => entry[sensorKey] !== null && entry[sensorKey] !== undefined)
      .map((entry) => ({
        time: entry.time,
        value: entry[sensorKey],
      }));
  }, [history, sensorKey]);

  // Tính min/max/delta
  const stats = useMemo(() => {
    if (chartData.length < 2) return null;
    const values = chartData.map((d) => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const first = values[0];
    const last = values[values.length - 1];
    const delta = last - first;
    return { min, max, delta };
  }, [chartData]);

  // Flash animation on value change
  useEffect(() => {
    if (previousValue !== undefined && previousValue !== value && cardRef.current) {
      cardRef.current.classList.remove("flash");
      void cardRef.current.offsetWidth;
      cardRef.current.classList.add("flash");
    }
  }, [value, previousValue]);

  return (
    <div
      ref={cardRef}
      className={`sensor-card status-${status}`}
      id={`sensor-${sensorKey}`}
    >
      {/* Header */}
      <div className="card-header">
        <div className="card-icon-wrapper">
          <div className="card-icon">{config.icon}</div>
          <span className="card-label-inline">{config.label}</span>
        </div>
        <span className={`card-status-badge badge-${status}`}>
          {statusLabel}
        </span>
      </div>

      {/* Value */}
      <div className="card-value-section">
        <span className={`card-value ${status}`}>
          {displayValue}
        </span>
        {config.unit && <span className="card-unit">{config.unit}</span>}
        {stats && (
          <span className={`card-delta ${stats.delta >= 0 ? "up" : "down"}`}>
            {stats.delta >= 0 ? "▲" : "▼"} {Math.abs(stats.delta).toFixed(1)}
          </span>
        )}
      </div>

      {/* Sparkline Chart */}
      <MiniSparkline data={chartData} sensorKey={sensorKey} status={status} />

      {/* Range Bar */}
      {hasData && (
        <div className="card-range">
          <span className="range-label">{config.min}</span>
          <div className="range-bar">
            <div
              className={`range-fill ${status}`}
              style={{ width: `${rangePercent}%` }}
            />
            {/* Normal range indicators */}
            <div
              className="range-normal-zone"
              style={{
                left: `${((config.normalRange[0] - config.min) / (config.max - config.min)) * 100}%`,
                width: `${((config.normalRange[1] - config.normalRange[0]) / (config.max - config.min)) * 100}%`,
              }}
            />
          </div>
          <span className="range-label">{config.max >= 10000 ? `${config.max / 1000}k` : config.max}</span>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="card-stats">
          <span className="stat-item">
            <span className="stat-label">Min</span>
            <span className="stat-value">{formatValue(stats.min)}</span>
          </span>
          <span className="stat-separator">·</span>
          <span className="stat-item">
            <span className="stat-label">Max</span>
            <span className="stat-value">{formatValue(stats.max)}</span>
          </span>
          <span className="stat-separator">·</span>
          <span className="stat-item">
            <span className="stat-label">Mẫu</span>
            <span className="stat-value">{chartData.length}</span>
          </span>
        </div>
      )}
    </div>
  );
}
