// ═══════════════════════════════════════════════════════════════
// Backend URL Detection
// ═══════════════════════════════════════════════════════════════
// 1. Nếu có NEXT_PUBLIC_API_URL (Vercel env) → dùng nó (VD: ngrok URL)
// 2. Nếu localhost:3000 → backend localhost:8000
// 3. Nếu 192.168.x.x:3000 → backend 192.168.x.x:8000

const getApiUrl = () => {
  if (typeof window === "undefined") return "http://localhost:8000";
  // Nếu là Vercel (không phải localhost/IP local) → cần env variable
  const host = window.location.hostname;
  if (host === "localhost" || host.startsWith("192.168.") || host.startsWith("10.")) {
    return `http://${host}:8000`;
  }
  // Vercel / domain khác → phải dùng NEXT_PUBLIC_API_URL
  return "http://localhost:8000";
};

const getWsUrl = () => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || getApiUrl();
  // Chuyển http→ws, https→wss
  const wsBase = apiUrl.replace("https://", "wss://").replace("http://", "ws://");
  return `${wsBase}/ws/sensor-data`;
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
