"use client";

import { useState, useEffect } from "react";
import useWebSocket from "@/hooks/useWebSocket";
import SensorCard from "@/components/SensorCard";
import AIAnalysis from "@/components/AIAnalysis";
import ControlPanel from "@/components/ControlPanel";
import AlertPanel from "@/components/AlertPanel";
import { getAllSensorKeys } from "@/lib/sensorConfig";
import Link from "next/link";

export default function Home() {
  const { sensorData, dataHistory, connectionStatus, lastUpdate } = useWebSocket();
  const [previousData, setPreviousData] = useState({});
  const sensorKeys = getAllSensorKeys();

  // Track previous values for flash animation
  useEffect(() => {
    if (sensorData) {
      setPreviousData((prev) => {
        return { ...sensorData };
      });
    }
  }, [sensorData]);

  const statusText = {
    connected: "Đang kết nối",
    disconnected: "Mất kết nối",
    connecting: "Đang kết nối...",
  };

  const statusClass = {
    connected: "",
    disconnected: "disconnected",
    connecting: "waiting",
  };

  const dataCount = dataHistory.length;

  return (
    <div className="app-container">
      {/* ─── Header ─── */}
      <header className="header">
        <div className="header-left">
          <div className="header-logo">🌱</div>
          <div>
            <h1 className="header-title">Sensor Monitor</h1>
            <p className="header-subtitle">Giám sát cảm biến nông nghiệp real-time</p>
          </div>
        </div>

        <div className="header-right">
          {dataCount > 0 && (
            <div className="data-counter">
              <span className="data-counter-number">{dataCount}</span>
              <span className="data-counter-label">mẫu</span>
            </div>
          )}
          <div className="connection-status">
            <div className={`status-dot ${statusClass[connectionStatus]}`} />
            <span>{statusText[connectionStatus]}</span>
          </div>
          {lastUpdate && (
            <span className="timestamp">
              Cập nhật: {lastUpdate.toLocaleTimeString("vi-VN")}
            </span>
          )}
          <Link href="/settings" style={{
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            width: "36px", 
            height: "36px", 
            background: "var(--bg-glass)", 
            border: "1px solid var(--border-color)", 
            borderRadius: "var(--radius-sm)",
            marginLeft: "8px",
            textDecoration: "none"
          }} title="Cài đặt Hệ thống (Zalo)">
            <span style={{ fontSize: "18px" }}>⚙️</span>
          </Link>
        </div>
      </header>

      {/* ─── Sensor Grid ─── */}
      {!sensorData ? (
        <div className="no-data">
          <div className="no-data-icon">📡</div>
          <h2 className="no-data-title">Chờ dữ liệu từ cảm biến...</h2>
          <p className="no-data-desc">
            Hệ thống đang chờ ESP32 gửi dữ liệu. Hãy đảm bảo thiết bị đã được
            kết nối và cấu hình đúng API endpoint.
          </p>
          <div className="no-data-steps">
            <div className="step-item">
              <span className="step-num">1</span>
              <span>Chạy backend: <code>python main.py</code></span>
            </div>
            <div className="step-item">
              <span className="step-num">2</span>
              <span>Chạy bridge: <code>python serial_bridge.py</code></span>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* ─── Cảnh Báo Sớm ─── */}
          <AlertPanel sensorData={sensorData} />

          {/* Section: Đất */}
          <div className="section-header">
            <span className="section-icon">🌍</span>
            <h2 className="section-title">Thông số đất</h2>
            <div className="section-line" />
          </div>
          <div className="sensor-grid">
            {["soil_temperature", "soil_moisture", "soil_ph", "ec", "nitrogen", "phosphorus", "potassium", "salinity"].map((key) => (
              <SensorCard
                key={key}
                sensorKey={key}
                value={sensorData[key]}
                previousValue={previousData[key]}
                history={dataHistory}
              />
            ))}
          </div>

          {/* Section: Môi trường */}
          <div className="section-header">
            <span className="section-icon">🌤️</span>
            <h2 className="section-title">Thông số môi trường</h2>
            <div className="section-line" />
          </div>
          <div className="sensor-grid">
            {["air_temperature", "air_humidity", "light_intensity"].map((key) => (
              <SensorCard
                key={key}
                sensorKey={key}
                value={sensorData[key]}
                previousValue={previousData[key]}
                history={dataHistory}
              />
            ))}
          </div>

          {/* Section: Điều khiển */}
          <ControlPanel />

          {/* ─── AI Analysis ─── */}
          <AIAnalysis sensorData={sensorData} />
        </>
      )}

      {/* ─── Footer ─── */}
      <footer className="footer">
        🌱 Sensor Monitoring System v2.0 — Powered by FastAPI & Next.js
      </footer>
    </div>
  );
}
