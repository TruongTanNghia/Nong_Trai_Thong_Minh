"use client";

import { useState } from "react";
import { analyzeData } from "@/lib/api";

export default function AIAnalysis({ sensorData }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyze = async () => {
    if (!sensorData) return;

    setLoading(true);
    setError(null);

    try {
      const result = await analyzeData(sensorData);
      setAnalysis(result);
    } catch (err) {
      setError("Không thể kết nối đến server phân tích. Vui lòng thử lại.");
      console.error("Analysis error:", err);
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
                {analysis.analysis}
              </div>
              <div className="analysis-timestamp">
                🕐 Phân tích lúc: {new Date(analysis.timestamp).toLocaleString("vi-VN")}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
