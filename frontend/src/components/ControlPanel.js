"use client";

import { useState, useEffect } from "react";
import { API_URL } from "@/lib/api";

const RELAYS = [
  { key: "heater", label: "Sưởi", icon: "🔥", color: "#ef4444", description: "Điều khiển máy sưởi", autoControlled: true },
  { key: "fan", label: "Quạt", icon: "🌀", color: "#06b6d4", description: "Điều khiển quạt thông gió", autoControlled: true },
  { key: "pump", label: "Bơm", icon: "💧", color: "#3b82f6", description: "Điều khiển máy bơm tưới", autoControlled: true },
  { key: "mist", label: "Phun sương", icon: "🌫️", color: "#a855f7", description: "Điều khiển phun sương", autoControlled: true },
  { key: "light", label: "Đèn", icon: "💡", color: "#f59e0b", description: "Điều khiển đèn chiếu sáng", autoControlled: false },
];

const RELAY_LABELS = { heater: "Sưởi", fan: "Quạt", pump: "Bơm", mist: "Phun sương", light: "Đèn" };

// ★ Bỏ nhóm "Ánh sáng → Đèn" — Đèn không tham gia auto control (firmware ESP32)
const THRESHOLD_CONFIG = [
  { group: "🌡️ Nhiệt độ không khí → Sưởi / Quạt", items: [
    { key: "temp_low", label: "Dưới ngưỡng → Bật Sưởi", unit: "°C", step: 0.5, min: 0, max: 50 },
    { key: "temp_high", label: "Trên ngưỡng → Bật Quạt", unit: "°C", step: 0.5, min: 0, max: 50 },
  ]},
  { group: "💨 Độ ẩm không khí → Phun sương", items: [
    { key: "air_humi_low", label: "Dưới ngưỡng → Bật Phun sương", unit: "%", step: 1, min: 0, max: 100 },
    { key: "air_humi_high", label: "Trên ngưỡng → Tắt Phun sương", unit: "%", step: 1, min: 0, max: 100 },
  ]},
  { group: "🌱 Độ ẩm đất → Bơm nước", items: [
    { key: "soil_humi_low", label: "Dưới ngưỡng → Bật Bơm", unit: "%", step: 1, min: 0, max: 100 },
    { key: "soil_humi_high", label: "Trên ngưỡng → Tắt Bơm", unit: "%", step: 1, min: 0, max: 100 },
  ]},
];

export default function ControlPanel() {
  const [relayStates, setRelayStates] = useState({
    heater: false, fan: false, pump: false, mist: false, light: false,
  });
  const [loading, setLoading] = useState({});
  const [autoMode, setAutoMode] = useState(false);
  const [autoLog, setAutoLog] = useState([]);
  const [autoLoading, setAutoLoading] = useState(false);
  const [thresholds, setThresholds] = useState({});
  const [editThresholds, setEditThresholds] = useState({});
  const [showSettings, setShowSettings] = useState(false);
  const [savingThresholds, setSavingThresholds] = useState(false);

  useEffect(() => {
    fetchRelayStatus();
    fetchAutoStatus();
    const interval = setInterval(() => {
      fetchRelayStatus();
      fetchAutoStatus();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchRelayStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/relay/status`);
      if (res.ok) setRelayStates(await res.json());
    } catch (err) { /* ignore */ }
  };

  const fetchAutoStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/auto/status`);
      if (res.ok) {
        const data = await res.json();
        setAutoMode(data.enabled);
        setAutoLog(data.log || []);
        setThresholds(data.thresholds || {});
      }
    } catch (err) { /* ignore */ }
  };

  const toggleRelay = async (relayKey) => {
    const newState = !relayStates[relayKey];
    setLoading((prev) => ({ ...prev, [relayKey]: true }));
    try {
      const res = await fetch(`${API_URL}/api/relay/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ relay: relayKey, state: newState }),
      });
      if (res.ok) setRelayStates((prev) => ({ ...prev, [relayKey]: newState }));
    } catch (err) {
      console.error(`Failed to toggle ${relayKey}:`, err);
    } finally {
      setLoading((prev) => ({ ...prev, [relayKey]: false }));
    }
  };

  const toggleAutoMode = async () => {
    setAutoLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/auto/toggle`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        setAutoMode(data.enabled);
      }
    } catch (err) {
      console.error("Failed to toggle auto mode:", err);
    } finally {
      setAutoLoading(false);
    }
  };

  const openSettings = () => {
    setEditThresholds({ ...thresholds });
    setShowSettings(true);
  };

  const handleThresholdChange = (key, value) => {
    setEditThresholds((prev) => ({ ...prev, [key]: parseFloat(value) || 0 }));
  };

  const saveThresholds = async () => {
    setSavingThresholds(true);
    try {
      const res = await fetch(`${API_URL}/api/auto/thresholds`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editThresholds),
      });
      if (res.ok) {
        const updated = await res.json();
        setThresholds(updated);
        setShowSettings(false);
      }
    } catch (err) {
      console.error("Failed to save thresholds:", err);
    } finally {
      setSavingThresholds(false);
    }
  };

  const activeCount = Object.values(relayStates).filter(Boolean).length;

  return (
    <div className="control-section">
      <div className="section-header">
        <span className="section-icon">🎛️</span>
        <h2 className="section-title">Điều khiển thiết bị</h2>
        <div className="section-line" />
        {activeCount > 0 && (
          <span className="active-count">{activeCount} đang bật</span>
        )}
      </div>

      {/* Auto Mode Bar */}
      <div className={`auto-mode-bar ${autoMode ? "auto-active" : ""}`}>
        <div className="auto-mode-left">
          <span className="auto-mode-icon">{autoMode ? "🤖" : "👋"}</span>
          <div>
            <div className="auto-mode-label">
              {autoMode ? "Chế độ TỰ ĐỘNG" : "Chế độ THỦ CÔNG"}
            </div>
            <div className="auto-mode-desc">
              {autoMode
                ? "ESP32 tự bật/tắt thiết bị dựa trên cảm biến"
                : "Bạn điều khiển bằng tay các thiết bị"}
            </div>
          </div>
        </div>
        <div className="auto-mode-right">
          {autoMode && (
            <button className="settings-btn" onClick={openSettings} title="Cài đặt ngưỡng">
              ⚙️ Cài đặt ngưỡng
            </button>
          )}
          <button
            className={`auto-toggle-btn ${autoMode ? "auto-on" : "auto-off"}`}
            onClick={toggleAutoMode}
            disabled={autoLoading}
          >
            {autoLoading ? (
              <span className="toggle-spinner" />
            ) : (
              <>
                <span>{autoMode ? "TỰ ĐỘNG" : "THỦ CÔNG"}</span>
                <div className={`toggle-track ${autoMode ? "track-on" : "track-off"}`}>
                  <div className={`toggle-thumb ${autoMode ? "thumb-on" : "thumb-off"}`} />
                </div>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Threshold Settings Modal */}
      {showSettings && (
        <div className="threshold-overlay" onClick={() => setShowSettings(false)}>
          <div className="threshold-modal" onClick={(e) => e.stopPropagation()}>
            <div className="threshold-modal-header">
              <div className="threshold-modal-title">
                <span>⚙️</span> Cài đặt ngưỡng tự động
              </div>
              <button className="threshold-close" onClick={() => setShowSettings(false)}>✕</button>
            </div>

            <div className="threshold-modal-body">
              <div className="threshold-note" style={{
                padding: "8px 12px",
                marginBottom: "12px",
                background: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: "8px",
                fontSize: "12px",
                color: "#f59e0b"
              }}>
                💡 Đèn không tham gia tự động — chỉ điều khiển thủ công
              </div>
              {THRESHOLD_CONFIG.map((group) => (
                <div key={group.group} className="threshold-group">
                  <div className="threshold-group-title">{group.group}</div>
                  <div className="threshold-inputs">
                    {group.items.map((item) => (
                      <div key={item.key} className="threshold-input-row">
                        <label className="threshold-label">{item.label}</label>
                        <div className="threshold-input-wrapper">
                          <button
                            className="threshold-step-btn"
                            onClick={() => handleThresholdChange(item.key, (editThresholds[item.key] || 0) - item.step)}
                          >−</button>
                          <input
                            type="number"
                            className="threshold-input"
                            value={editThresholds[item.key] ?? ""}
                            onChange={(e) => handleThresholdChange(item.key, e.target.value)}
                            step={item.step}
                            min={item.min}
                            max={item.max}
                          />
                          <span className="threshold-unit">{item.unit}</span>
                          <button
                            className="threshold-step-btn"
                            onClick={() => handleThresholdChange(item.key, (editThresholds[item.key] || 0) + item.step)}
                          >+</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="threshold-modal-footer">
              <button className="threshold-cancel" onClick={() => setShowSettings(false)}>Hủy</button>
              <button className="threshold-save" onClick={saveThresholds} disabled={savingThresholds}>
                {savingThresholds ? "Đang lưu..." : "💾 Lưu ngưỡng"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Relay Cards */}
      <div className="control-grid">
        {RELAYS.map((relay) => {
          const isOn = relayStates[relay.key];
          const isLoading = loading[relay.key];
          // ★ Đèn luôn cho phép điều khiển tay (không bị disable khi auto mode)
          const isDisabledByAuto = autoMode && relay.autoControlled;

          return (
            <div
              key={relay.key}
              className={`control-card ${isOn ? "control-on" : "control-off"} ${isDisabledByAuto ? "auto-controlled" : ""}`}
              style={{ "--relay-color": relay.color }}
            >
              <div className="control-card-header">
                <div className="control-icon-wrapper">
                  <span className="control-icon">{relay.icon}</span>
                  <div>
                    <div className="control-label">{relay.label}</div>
                    <div className="control-desc">
                      {isDisabledByAuto
                        ? "Tự động"
                        : !relay.autoControlled
                          ? "Chỉ thủ công"
                          : relay.description}
                    </div>
                  </div>
                </div>
                <div className={`control-status-dot ${isOn ? "on" : "off"}`} />
              </div>

              <button
                className={`control-toggle ${isOn ? "toggle-on" : "toggle-off"}`}
                onClick={() => toggleRelay(relay.key)}
                disabled={isLoading || isDisabledByAuto}
                id={`relay-${relay.key}`}
              >
                {isLoading ? (
                  <span className="toggle-spinner" />
                ) : (
                  <>
                    <span className="toggle-state">{isOn ? "ON" : "OFF"}</span>
                    <div className={`toggle-track ${isOn ? "track-on" : "track-off"}`}>
                      <div className={`toggle-thumb ${isOn ? "thumb-on" : "thumb-off"}`} />
                    </div>
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      {/* Auto Control Log */}
      {autoMode && autoLog.length > 0 && (
        <div className="auto-log">
          <div className="auto-log-header">
            <span>📋 Nhật ký tự động</span>
            <span className="auto-log-count">{autoLog.length} hành động</span>
          </div>
          <div className="auto-log-list">
            {[...autoLog].reverse().slice(0, 10).map((entry, i) => (
              <div key={i} className="auto-log-item">
                <span className="log-time">{entry.time}</span>
                <span className={`log-badge ${entry.state ? "log-on" : "log-off"}`}>
                  {RELAY_LABELS[entry.relay] || entry.relay} {entry.state ? "BẬT" : "TẮT"}
                </span>
                <span className="log-reason">{entry.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
