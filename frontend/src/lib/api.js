const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getLatestData() {
  const res = await fetch(`${API_URL}/api/sensor-data/latest`);
  if (!res.ok) throw new Error("Failed to fetch latest data");
  return res.json();
}

export async function analyzeData(sensorData = null) {
  const res = await fetch(`${API_URL}/api/analysis`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sensor_data: sensorData }),
  });
  if (!res.ok) throw new Error("Failed to analyze data");
  return res.json();
}

export async function fetchZaloConfig() {
  const res = await fetch(`${API_URL}/api/zalo/config`);
  if (!res.ok) throw new Error("Failed to fetch Zalo config");
  return res.json();
}

export async function saveZaloConfig(botToken, chatId, sendInterval) {
  const res = await fetch(`${API_URL}/api/zalo/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_token: botToken, chat_id: chatId, send_interval: sendInterval }),
  });
  if (!res.ok) throw new Error("Failed to save Zalo config");
  return res.json();
}

export async function fetchZaloId(botToken) {
  const res = await fetch(`${API_URL}/api/zalo/fetch-id`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bot_token: botToken }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to fetch Zalo ID");
  return data;
}

export async function toggleZaloAuto(autoSend) {
  const res = await fetch(`${API_URL}/api/zalo/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ auto_send: autoSend }),
  });
  if (!res.ok) throw new Error("Failed to toggle Zalo auto send");
  return res.json();
}
