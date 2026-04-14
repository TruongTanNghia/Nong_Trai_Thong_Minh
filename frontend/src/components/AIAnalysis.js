"use client";

import { useState } from "react";

// ★ Gọi qua Next.js API route — key AN TOÀN ở server, KHÔNG lộ ra browser

export default function AIAnalysis({ sensorData }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!sensorData) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sensor_data: sensorData }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `Lỗi server (${res.status})`);
      }

      setAnalysis({
        text: data.text,
        modelName: data.modelName,
        timestamp: data.timestamp,
      });
    } catch (err) {
      setError(err.message || "Không thể kết nối đến AI. Vui lòng thử lại.");
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
            <span>Phân tích AI</span>
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
              <p>AI đang phân tích dữ liệu cảm biến...</p>
            </div>
          )}

          {analysis && (
            <>
              <div className="analysis-content">
                {analysis.text}
              </div>
              <div className="analysis-timestamp">
                🕐 Phân tích lúc: {new Date(analysis.timestamp).toLocaleString("vi-VN")}
                &nbsp;|&nbsp; 🤖 Model: {analysis.modelName}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
