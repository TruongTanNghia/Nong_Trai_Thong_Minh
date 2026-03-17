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
