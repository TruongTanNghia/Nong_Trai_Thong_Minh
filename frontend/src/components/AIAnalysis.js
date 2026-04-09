"use client";

import { useState } from "react";

// ★ Gọi Gemma 3 27B trực tiếp từ Frontend — không cần backend
const GEMINI_API_KEY = process.env.NEXT_PUBLIC_GEMINI_KEY || "AIzaSyApSruI-xMRpWQlu0ZhdoM2shP4HF-OY2w";
const GEMINI_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key=${GEMINI_API_KEY}`;

async function callGemini(sensorData) {
  const prompt = `Bạn là chuyên gia nông nghiệp thông minh. Phân tích dữ liệu cảm biến nhà kính sau và đưa ra đánh giá + khuyến nghị ngắn gọn bằng tiếng Việt:

📊 Dữ liệu:
- Nhiệt độ không khí: ${sensorData.air_temperature ?? "N/A"}°C
- Độ ẩm không khí: ${sensorData.air_humidity ?? "N/A"}%
- Nhiệt độ đất: ${sensorData.soil_temperature ?? "N/A"}°C
- Độ ẩm đất: ${sensorData.soil_moisture ?? "N/A"}%
- pH đất: ${sensorData.soil_ph ?? "N/A"}
- EC (độ dẫn điện): ${sensorData.ec ?? "N/A"} µS/cm
- Độ mặn: ${sensorData.salinity ?? "N/A"}
- Nitrogen (N): ${sensorData.nitrogen ?? "N/A"} mg/kg
- Phosphorus (P): ${sensorData.phosphorus ?? "N/A"} mg/kg
- Potassium (K): ${sensorData.potassium ?? "N/A"} mg/kg

Trả lời theo format:
🌡️ ĐÁNH GIÁ TỔNG QUAN: (1-2 câu)
⚠️ CẢNH BÁO: (nếu có thông số bất thường)
💡 KHUYẾN NGHỊ: (3-5 gợi ý cụ thể)
🌱 ĐÁNH GIÁ CÂY TRỒNG: (phù hợp trồng gì)`;

  const res = await fetch(GEMINI_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.7, maxOutputTokens: 1000 },
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini API lỗi (${res.status}): ${errText.slice(0, 200)}`);
  }

  const data = await res.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error("Gemini không trả về kết quả");
  return text;
}

export default function AIAnalysis({ sensorData }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!sensorData) return;

    setLoading(true);
    setError(null);

    try {
      const text = await callGemini(sensorData);
      setAnalysis({
        text,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      setError(err.message || "Không thể kết nối đến Gemini AI. Vui lòng thử lại.");
      console.error("AI Analysis error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="analysis-section">
      <div className="analysis-card">
        <div className="analysis-header">
          <div className="analysis-title">
            <div className="analysis-title-icon">🤖</div>
            <span>Phân tích AI (Gemini)</span>
          </div>
          <button
            className="analyze-btn"
            onClick={handleAnalyze}
            disabled={loading || !sensorData}
          >
            {loading ? (
              <>
                <div className="spinner" />
                Đang phân tích...
              </>
            ) : (
              <>✨ Phân tích ngay</>
            )}
          </button>
        </div>

        <div className="analysis-body">
          {error && (
            <div className="analysis-placeholder" style={{ color: "var(--accent-red)" }}>
              <div className="analysis-placeholder-icon">⚠️</div>
              <p>{error}</p>
            </div>
          )}

          {!analysis && !error && !loading && (
            <div className="analysis-placeholder">
              <div className="analysis-placeholder-icon">🧠</div>
              <p>Bấm &quot;Phân tích ngay&quot; để AI đánh giá tình trạng đất và môi trường, đưa ra khuyến nghị cho bạn.</p>
            </div>
          )}

          {loading && !analysis && (
            <div className="analysis-placeholder">
              <div className="analysis-placeholder-icon" style={{ animation: "spin 2s linear infinite" }}>🔄</div>
              <p>Gemini AI đang phân tích dữ liệu cảm biến...</p>
            </div>
          )}

          {analysis && (
            <>
              <div className="analysis-content">
                {analysis.text}
              </div>
              <div className="analysis-timestamp">
                🕐 Phân tích lúc: {new Date(analysis.timestamp).toLocaleString("vi-VN")}
                &nbsp;|&nbsp; 🤖 Model: Gemma 3 27B
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
