"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchZaloConfig, saveZaloConfig, fetchZaloId, toggleZaloAuto } from "@/lib/api";

export default function SettingsPage() {
  const [botToken, setBotToken] = useState("");
  const [chatId, setChatId] = useState("");
  const [autoSend, setAutoSend] = useState(true);
  const [sendInterval, setSendInterval] = useState(30);
  
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingId, setIsFetchingId] = useState(false);
  const [message, setMessage] = useState({ text: "", type: "" });

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const config = await fetchZaloConfig();
      if (config) {
        setBotToken(config.bot_token || "");
        setChatId(config.chat_id || "");
        setAutoSend(config.auto_send !== false);
        setSendInterval(config.send_interval || 30);
      }
    } catch (error) {
      showMessage("Không thể tải cấu hình Zalo hiện tại.", "error");
    }
  };

  const showMessage = (text, type) => {
    setMessage({ text, type });
    setTimeout(() => setMessage({ text: "", type: "" }), 5000);
  };

  const handleFetchId = async () => {
    if (!botToken) {
      showMessage("Vui lòng nhập Bot Token trước khi lấy ID.", "error");
      return;
    }
    
    setIsFetchingId(true);
    showMessage("Đang quét tin nhắn Zalo...", "info");
    
    try {
      const data = await fetchZaloId(botToken);
      if (data && data.chat_id) {
        setChatId(data.chat_id);
        showMessage("Lấy Chat ID thành công! Nhớ bấm Lưu Cấu Hình nhé.", "success");
      }
    } catch (error) {
      showMessage(error.message || "Lỗi khi lấy Chat ID. Vui lòng thử nhắn tin cho bot rồi làm lại.", "error");
    } finally {
      setIsFetchingId(false);
    }
  };

  const handleSaveConfig = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    
    try {
      await saveZaloConfig(botToken, chatId, parseInt(sendInterval));
      await toggleZaloAuto(autoSend);
      showMessage("Đã lưu cấu hình Zalo thành công!", "success");
    } catch (error) {
      showMessage("Lỗi khi lưu cấu hình", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleAuto = async (e) => {
    const newValue = e.target.checked;
    setAutoSend(newValue);
    try {
      await toggleZaloAuto(newValue);
      showMessage(`Đã ${newValue ? 'bật' : 'tắt'} gửi tự động Zalo`, "success");
    } catch (error) {
      setAutoSend(!newValue); // revert on fail
      showMessage("Lỗi khi thay đổi trạng thái tự động", "error");
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="header-left">
          <Link href="/" className="back-btn">
            <span className="back-icon">←</span>
            <span>Quay lại Dashboard</span>
          </Link>
          <div style={{ marginLeft: "20px" }}>
            <h1 className="header-title">Cài Đặt Hệ Thống</h1>
            <p className="header-subtitle">Cấu hình Zalo Bot & Thông báo</p>
          </div>
        </div>
      </header>

      <div className="settings-container" style={{ maxWidth: "600px", margin: "0 auto", marginTop: "40px" }}>
        <div className="settings-card card">
          <div className="card-header">
            <h2 className="section-title" style={{ margin: 0 }}>Cấu hình Zalo ZApps</h2>
          </div>
          <div className="card-body" style={{ padding: "20px", background: "var(--bg-card)", borderRadius: "var(--radius-lg)", border: "1px solid var(--border-color)"}}>
            
            {message.text && (
              <div className={`message-box ${message.type}`} style={{
                padding: "10px 15px", 
                borderRadius: "var(--radius-md)", 
                marginBottom: "20px",
                background: message.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : message.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(99, 102, 241, 0.1)',
                color: message.type === 'error' ? 'var(--accent-red)' : message.type === 'success' ? 'var(--accent-green)' : 'var(--accent-blue)',
                border: `1px solid ${message.type === 'error' ? 'rgba(239, 68, 68, 0.2)' : message.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(99, 102, 241, 0.2)'}`
              }}>
                {message.text}
              </div>
            )}

            <form onSubmit={handleSaveConfig} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              
              <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <label style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-secondary)" }}>Bot Token</label>
                <input 
                  type="text" 
                  value={botToken}
                  onChange={(e) => setBotToken(e.target.value)}
                  placeholder="Nhập Token của Zalo Bot..."
                  style={{
                    padding: "12px",
                    background: "rgba(0,0,0,0.2)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    color: "white",
                    fontFamily: "var(--font-mono)",
                    fontSize: "13px"
                  }}
                  required
                />
              </div>

              <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <label style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-secondary)" }}>Chat ID</label>
                <div style={{ display: "flex", gap: "10px" }}>
                  <input 
                    type="text" 
                    value={chatId}
                    onChange={(e) => setChatId(e.target.value)}
                    placeholder="Nhập hoặc ấn Lấy ID..."
                    style={{
                      flex: 1,
                      padding: "12px",
                      background: "rgba(0,0,0,0.2)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "var(--radius-sm)",
                      color: "white",
                      fontFamily: "var(--font-mono)",
                      fontSize: "13px"
                    }}
                    required
                  />
                  <button 
                    type="button" 
                    onClick={handleFetchId}
                    disabled={isFetchingId || !botToken}
                    style={{
                      padding: "0 20px",
                      background: "var(--bg-glass)",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-primary)",
                      borderRadius: "var(--radius-sm)",
                      cursor: (isFetchingId || !botToken) ? "not-allowed" : "pointer",
                      opacity: (isFetchingId || !botToken) ? 0.5 : 1,
                      fontWeight: 600
                    }}
                  >
                    {isFetchingId ? "Đang quét..." : "Lấy ID"}
                  </button>
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  * Gửi một tin nhắn bất kỳ cho Bot trên Zalo trước khi nhấn nút "Lấy ID".
                </p>
              </div>

              <div className="form-group" style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                <label style={{ fontSize: "14px", fontWeight: "600", color: "var(--text-secondary)" }}>Chu kỳ gửi (giây)</label>
                <input 
                  type="number" 
                  value={sendInterval}
                  onChange={(e) => setSendInterval(Math.max(10, parseInt(e.target.value) || 10))}
                  min="10"
                  step="5"
                  style={{
                    padding: "12px",
                    background: "rgba(0,0,0,0.2)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "var(--radius-sm)",
                    color: "white",
                    fontFamily: "var(--font-mono)",
                    fontSize: "13px",
                    maxWidth: "200px"
                  }}
                />
                <p style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  Tối thiểu 10 giây. Mặc định 30 giây.
                </p>
              </div>

              <div className="form-group" style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "10px" }}>
                <label className="css-toggle" style={{ display: "flex", alignItems: "center", cursor: "pointer", gap: "10px" }}>
                  <input 
                    type="checkbox" 
                    checked={autoSend} 
                    onChange={handleToggleAuto}
                    style={{ width: "18px", height: "18px" }}
                  />
                  <span style={{ fontSize: "14px", fontWeight: "500" }}>Gửi dữ liệu tự động (mỗi {sendInterval}s)</span>
                </label>
              </div>

              <button 
                type="submit" 
                disabled={isLoading}
                style={{
                  marginTop: "10px",
                  padding: "14px",
                  background: "var(--gradient-blue)",
                  color: "white",
                  border: "none",
                  borderRadius: "var(--radius-md)",
                  fontWeight: "bold",
                  fontSize: "15px",
                  cursor: isLoading ? "not-allowed" : "pointer",
                  opacity: isLoading ? 0.7 : 1,
                  boxShadow: "0 4px 14px rgba(99, 102, 241, 0.4)"
                }}
              >
                {isLoading ? "Đang lưu..." : "Lưu Cấu Hình"}
              </button>
            </form>
          </div>
        </div>
      </div>

    </div>
  );
}
