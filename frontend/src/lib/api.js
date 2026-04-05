// Tự động phát hiện backend URL dựa trên hostname trình duyệt
// Nếu mở web bằng http://192.168.0.100:3000 → backend = http://192.168.0.100:8000
// Nếu mở web bằng http://localhost:3000 → backend = http://localhost:8000
const getApiUrl = () => {
  if (typeof window === "undefined") return "http://localhost:8000";
  const host = window.location.hostname;
  return `http://${host}:8000`;
};

const getWsUrl = () => {
  if (typeof window === "undefined") return "ws://localhost:8000/ws/sensor-data";
  const host = window.location.hostname;
  return `ws://${host}:8000/ws/sensor-data`;
};

export const API_URL = process.env.NEXT_PUBLIC_API_URL || getApiUrl();
export const WS_URL = process.env.NEXT_PUBLIC_WS_URL || getWsUrl();

// AI Analysis — gọi backend phân tích dữ liệu cảm biến
export async function analyzeData(sensorData) {
  const res = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sensor_data: sensorData }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

// ─── Zalo Config ─────────────────────────────────────────

export async function fetchZaloConfig() {
  const res = await fetch(`${API_URL}/api/zalo/config`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function saveZaloConfig(botToken, chatId, sendInterval) {
  const res = await fetch(`${API_URL}/api/zalo/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_token: botToken, chat_id: chatId, send_interval: sendInterval }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function fetchZaloId(botToken) {
  const res = await fetch(`${API_URL}/api/zalo/fetch-id`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_token: botToken }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

export async function toggleZaloAuto(autoSend) {
  const res = await fetch(`${API_URL}/api/zalo/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_send: autoSend }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}
