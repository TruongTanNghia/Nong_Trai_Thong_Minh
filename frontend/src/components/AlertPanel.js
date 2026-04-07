"use client";

import { useState, useEffect, useRef } from "react";
import { getSensorConfig, getStatus, getAllSensorKeys, formatValue } from "@/lib/sensorConfig";

/**
 * AlertPanel — Cảnh báo sớm khi thông số vượt mức
 * Tự động kiểm tra tất cả sensor data dựa trên normalRange/warningRange
 */
export default function AlertPanel({ sensorData }) {
  const [alerts, setAlerts] = useState([]);
  const [dismissed, setDismissed] = useState({});
  const [isCollapsed, setIsCollapsed] = useState(false);
  const prevAlertCountRef = useRef(0);
  const audioRef = useRef(null);

  useEffect(() => {
    if (!sensorData) return;

    const newAlerts = [];
    const keys = getAllSensorKeys();

    for (const key of keys) {
      const value = sensorData[key];
      if (value === null || value === undefined) continue;

      const config = getSensorConfig(key);
      if (!config) continue;

      const status = getStatus(key, value);
      if (status === "normal") continue;

      const [normalMin, normalMax] = config.normalRange;
      const [warnMin, warnMax] = config.warningRange;

      let severity, message, suggestion;

      if (status === "danger") {
        severity = "danger";
        if (value < warnMin) {
          message = `${config.label} QUÁ THẤP: ${formatValue(value)}${config.unit}`;
          suggestion = `Giá trị bình thường: ${normalMin}–${normalMax}${config.unit}. Cần tăng ngay!`;
        } else {
          message = `${config.label} QUÁ CAO: ${formatValue(value)}${config.unit}`;
          suggestion = `Giá trị bình thường: ${normalMin}–${normalMax}${config.unit}. Cần giảm ngay!`;
        }
      } else {
        severity = "warning";
        if (value < normalMin) {
          message = `${config.label} hơi thấp: ${formatValue(value)}${config.unit}`;
          suggestion = `Đang gần ngưỡng nguy hiểm (${warnMin}${config.unit}). Nên điều chỉnh.`;
        } else {
          message = `${config.label} hơi cao: ${formatValue(value)}${config.unit}`;
          suggestion = `Đang gần ngưỡng nguy hiểm (${warnMax}${config.unit}). Nên điều chỉnh.`;
        }
      }

      newAlerts.push({
        key,
        icon: config.icon,
        severity,
        message,
        suggestion,
        value,
        unit: config.unit,
        normalRange: config.normalRange,
      });
    }

    // Sort: danger first, then warning
    newAlerts.sort((a, b) => {
      if (a.severity === "danger" && b.severity !== "danger") return -1;
      if (a.severity !== "danger" && b.severity === "danger") return 1;
      return 0;
    });

    setAlerts(newAlerts);

    // Auto expand when new danger alerts appear
    const dangerCount = newAlerts.filter((a) => a.severity === "danger").length;
    if (dangerCount > prevAlertCountRef.current) {
      setIsCollapsed(false);
    }
    prevAlertCountRef.current = dangerCount;
  }, [sensorData]);

  const dismissAlert = (key) => {
    setDismissed((prev) => ({ ...prev, [key]: true }));
  };

  const clearDismissed = () => {
    setDismissed({});
  };

  const visibleAlerts = alerts.filter((a) => !dismissed[a.key]);
  const dangerCount = visibleAlerts.filter((a) => a.severity === "danger").length;
  const warningCount = visibleAlerts.filter((a) => a.severity === "warning").length;
  const totalDismissed = Object.keys(dismissed).length;

  if (alerts.length === 0) return null;

  return (
    <div className="alert-panel">
      {/* Header */}
      <div
        className={`alert-panel-header ${dangerCount > 0 ? "alert-danger-bg" : "alert-warning-bg"}`}
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <div className="alert-header-left">
          <span className={`alert-pulse ${dangerCount > 0 ? "pulse-danger" : "pulse-warning"}`} />
          <span className="alert-header-icon">
            {dangerCount > 0 ? "🚨" : "⚠️"}
          </span>
          <div>
            <div className="alert-header-title">
              Cảnh Báo Sớm
            </div>
            <div className="alert-header-count">
              {dangerCount > 0 && (
                <span className="alert-badge-danger">{dangerCount} nguy hiểm</span>
              )}
              {warningCount > 0 && (
                <span className="alert-badge-warning">{warningCount} lưu ý</span>
              )}
            </div>
          </div>
        </div>
        <div className="alert-header-right">
          {totalDismissed > 0 && (
            <button className="alert-restore-btn" onClick={(e) => { e.stopPropagation(); clearDismissed(); }}>
              Hiện lại ({totalDismissed})
            </button>
          )}
          <span className={`alert-chevron ${isCollapsed ? "" : "chevron-open"}`}>▸</span>
        </div>
      </div>

      {/* Alert list */}
      {!isCollapsed && visibleAlerts.length > 0 && (
        <div className="alert-list">
          {visibleAlerts.map((alert) => (
            <div
              key={alert.key}
              className={`alert-item ${alert.severity === "danger" ? "alert-item-danger" : "alert-item-warning"}`}
            >
              <div className="alert-item-icon">
                {alert.icon}
              </div>
              <div className="alert-item-content">
                <div className="alert-item-message">
                  {alert.severity === "danger" ? "🔴" : "🟡"} {alert.message}
                </div>
                <div className="alert-item-suggestion">
                  💡 {alert.suggestion}
                </div>
                <div className="alert-item-range">
                  Khoảng tốt: {alert.normalRange[0]}–{alert.normalRange[1]}{alert.unit}
                </div>
              </div>
              <button
                className="alert-dismiss-btn"
                onClick={() => dismissAlert(alert.key)}
                title="Ẩn cảnh báo này"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {!isCollapsed && visibleAlerts.length === 0 && totalDismissed > 0 && (
        <div className="alert-all-dismissed">
          ✅ Đã ẩn tất cả cảnh báo.
          <button className="alert-restore-link" onClick={clearDismissed}>Hiện lại</button>
        </div>
      )}
    </div>
  );
}
