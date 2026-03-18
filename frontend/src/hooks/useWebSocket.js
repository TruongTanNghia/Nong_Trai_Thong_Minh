"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getAllSensorKeys } from "@/lib/sensorConfig";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/sensor-data";
const MAX_HISTORY = 60; // Giữ 60 data points trong buffer

export default function useWebSocket() {
  const [sensorData, setSensorData] = useState(null);
  const [dataHistory, setDataHistory] = useState([]); // Array of {timestamp, ...values}
  const [connectionStatus, setConnectionStatus] = useState("disconnected");
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);
  const reconnectTimeout = useRef(null);
  const reconnectAttempts = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus("connecting");

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnectionStatus("connected");
        reconnectAttempts.current = 0;
        console.log("✅ WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "ping") return;

          setSensorData(data);
          setLastUpdate(new Date());

          // Thêm vào history buffer
          setDataHistory((prev) => {
            const now = new Date();
            const entry = {
              time: now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
              timestamp: now.getTime(),
              ...data,
            };
            const newHistory = [...prev, entry];
            // Giữ max N entries
            if (newHistory.length > MAX_HISTORY) {
              return newHistory.slice(newHistory.length - MAX_HISTORY);
            }
            return newHistory;
          });
        } catch (e) {
          console.error("Failed to parse WS message:", e);
        }
      };

      ws.onclose = () => {
        setConnectionStatus("disconnected");
        console.log("❌ WebSocket disconnected");
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
        reconnectAttempts.current++;
        reconnectTimeout.current = setTimeout(connect, delay);
      };

      ws.onerror = () => {
        // Dùng warn thay error để tránh Next.js dev overlay hiển thị lỗi đỏ
        console.warn("⚠️ WebSocket connection error, will reconnect...");
        ws.close();
      };
    } catch (err) {
      console.warn("Failed to create WebSocket:", err);
      setConnectionStatus("disconnected");
    }
  }, []);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionStatus("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { sensorData, dataHistory, connectionStatus, lastUpdate, reconnect: connect };
}
