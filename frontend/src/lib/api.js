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
