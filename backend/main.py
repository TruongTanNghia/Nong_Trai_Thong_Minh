"""
FastAPI Backend v3 - Real-time Sensor Monitoring & AI Analysis
★ ESP32 giao tiếp trực tiếp qua WiFi HTTP (không cần serial_bridge.py)
  - POST /api/esp32/upload : ESP32 push toàn bộ data mỗi 3s
  - GET  /api/esp32/command: ESP32 poll lệnh từ web mỗi 1s
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from zalo_utils import load_zalo_config, save_zalo_config, fetch_chat_id_from_updates, send_zalo_text, format_sensor_message

load_dotenv()

# ─── Pydantic Schemas ────────────────────────────────────────────

class SensorData(BaseModel):
    soil_temperature: Optional[float] = Field(None, description="°C")
    soil_moisture: Optional[float] = Field(None, description="%")
    soil_ph: Optional[float] = Field(None, description="pH")
    ec: Optional[float] = Field(None, description="µS/cm")
    nitrogen: Optional[float] = Field(None, description="mg/kg")
    phosphorus: Optional[float] = Field(None, description="mg/kg")
    potassium: Optional[float] = Field(None, description="mg/kg")
    salinity: Optional[float] = Field(None, description="mg/L")
    air_temperature: Optional[float] = Field(None, description="°C")
    air_humidity: Optional[float] = Field(None, description="%")
    light_intensity: Optional[float] = Field(None, description="lux")


class SensorDataWithTimestamp(SensorData):
    timestamp: str = ""


class AnalysisRequest(BaseModel):
    sensor_data: Optional[SensorData] = None


class AnalysisResponse(BaseModel):
    analysis: str
    timestamp: str


class RelayCommand(BaseModel):
    relay: str  # heater, fan, pump, mist, light
    state: bool


# ─── WebSocket Manager ───────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)


# ─── App Setup ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(zalo_periodic_task())
    yield

app = FastAPI(
    title="Sensor Monitoring API",
    description="Real-time agricultural sensor monitoring with AI analysis",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

# ─── In-Memory State ─────────────────────────────────────────────

# Sensor data (latest)
latest_data: dict = {}

# Relay states (ESP32 → Web, source of truth from ESP32)
relay_states: dict = {
    "heater": False,
    "fan": False,
    "pump": False,
    "mist": False,
    "light": False,
}

# Auto mode (synced from ESP32)
auto_mode: bool = True  # ESP32 mặc định AUTO

# Thresholds (synced from ESP32)
auto_thresholds: dict = {
    "temp_low": 20.0,
    "temp_high": 30.0,
    "air_humi_low": 60.0,
    "air_humi_high": 80.0,
    "soil_humi_low": 30.0,
    "soil_humi_high": 60.0,
}

auto_control_log: list = []

# ★ ESP32 WiFi direct — command queue (merged dict)
# Khi user thao tác trên web → ghi vào đây
# ESP32 poll GET /api/esp32/command → lấy ra và xóa
esp32_pending_commands: dict = {}

# ★ ESP32 device info
esp32_device_info: dict = {}

# Legacy: relay_command_queue cho serial_bridge (backward compatible)
relay_command_queue: list = []

# ─── Zalo Settings ───────────────────────────────────────────────
zalo_config = load_zalo_config()
zalo_auto_send: bool = True
zalo_send_interval: int = zalo_config.get("send_interval", 30)

# ★ Cảnh báo Zalo khi thông số vượt mức
ALERT_THRESHOLDS = {
    "air_temperature": {"label": "Nhiệt độ KK", "unit": "°C", "normal": [20, 32], "warning": [15, 38]},
    "air_humidity":    {"label": "Độ ẩm KK",    "unit": "%",  "normal": [40, 80], "warning": [25, 90]},
    "soil_temperature":{"label": "Nhiệt độ đất","unit": "°C", "normal": [15, 30], "warning": [10, 35]},
    "soil_moisture":   {"label": "Độ ẩm đất",   "unit": "%",  "normal": [30, 70], "warning": [20, 80]},
    "soil_ph":         {"label": "pH đất",      "unit": "",   "normal": [5.5, 7.5], "warning": [4.5, 8.5]},
    "ec":              {"label": "EC",           "unit": "µS/cm", "normal": [200, 800], "warning": [100, 1200]},
    "salinity":        {"label": "Độ mặn",      "unit": "mg/L", "normal": [0, 200], "warning": [0, 400]},
}
alert_cooldown: dict = {}  # {sensor_key: last_alert_time} — tránh spam
ALERT_COOLDOWN_SECONDS = 300  # 5 phút giữa mỗi lần cảnh báo cùng sensor

import time as _time

def check_and_send_zalo_alerts(sensor_data: dict):
    """Kiểm tra thông số và gửi cảnh báo Zalo nếu vượt mức."""
    global alert_cooldown
    token = zalo_config.get("bot_token")
    chat_id = zalo_config.get("chat_id")
    if not token or not chat_id:
        return

    now = _time.time()
    alerts = []

    for key, cfg in ALERT_THRESHOLDS.items():
        value = sensor_data.get(key)
        if value is None:
            continue

        normal_min, normal_max = cfg["normal"]
        warn_min, warn_max = cfg["warning"]
        label = cfg["label"]
        unit = cfg["unit"]

        severity = None
        if value < warn_min or value > warn_max:
            severity = "🔴 NGUY HIỂM"
        elif value < normal_min or value > normal_max:
            severity = "🟡 LƯU Ý"

        if severity:
            # Cooldown check
            last = alert_cooldown.get(key, 0)
            if now - last < ALERT_COOLDOWN_SECONDS:
                continue
            alert_cooldown[key] = now

            direction = "THẤP" if (value < normal_min) else "CAO"
            alerts.append(f"{severity}: {label} QUÁ {direction}: {value}{unit} (bình thường: {normal_min}-{normal_max}{unit})")

    if alerts:
        msg = f"🚨 CẢNH BÁO NHÀ KÍNH 🚨\n"
        msg += f"⏰ {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}\n\n"
        msg += "\n".join(alerts)
        msg += f"\n\n💡 Kiểm tra hệ thống ngay!"

        try:
            send_zalo_text(token, chat_id, msg)
            print(f"📱 Đã gửi {len(alerts)} cảnh báo Zalo!")
        except Exception as e:
            print(f"⚠️ Lỗi gửi cảnh báo Zalo: {e}")


async def zalo_periodic_task():
    while True:
        try:
            await asyncio.sleep(zalo_send_interval)
            if not zalo_auto_send:
                continue
            token = zalo_config.get("bot_token")
            chat_id = zalo_config.get("chat_id")
            if token and chat_id and latest_data:
                msg = format_sensor_message(latest_data)
                await asyncio.to_thread(send_zalo_text, token, chat_id, msg)
        except Exception as e:
            print(f"⚠️ Lỗi zalo_periodic_task: {e}")


# ═══════════════════════════════════════════════════════════════════
# ★★★ ESP32 WiFi Direct Endpoints (MỚI - thay thế serial_bridge)
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/esp32/upload")
async def esp32_upload(data: dict):
    """
    ★ ESP32 gửi TOÀN BỘ state lên đây mỗi 3 giây qua WiFi HTTP.
    Payload bao gồm: sensor data + relay states + mode + settings + wifi info.
    ESP32 là master — backend chỉ nhận và hiển thị.
    """
    global latest_data, relay_states, auto_mode, auto_thresholds, esp32_device_info

    device_id = data.get("device_id", "unknown")
    has_valid = data.get("hasValidData", False)
    mode_str = data.get("mode", "AUTO")
    esp_ip = data.get("ip", "")
    rssi = data.get("wifi_rssi", 0)

    # ★ LOG: Hiển thị rõ ESP32 đã kết nối
    if not esp32_device_info:
        print("")
        print("═" * 50)
        print("🟢 ESP32 ĐÃ KẾT NỐI THÀNH CÔNG!")
        print(f"   📡 Device: {device_id}")
        print(f"   🌐 IP ESP32: {esp_ip}")
        print(f"   📶 WiFi RSSI: {rssi} dBm")
        print(f"   🔄 Mode: {mode_str}")
        print("═" * 50)
        print("")

    # ★ LOG: Hiển thị data mỗi lần upload
    if has_valid:
        print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] ESP32 → "
              f"T:{data.get('airTemp')}°C  "
              f"H:{data.get('airHumi')}%  "
              f"Soil:{data.get('soilHumi')}%  "
              f"pH:{data.get('ph')}  "
              f"Mode:{mode_str}  "
              f"RSSI:{rssi}dBm")
    else:
        print(f"📡 [{datetime.now().strftime('%H:%M:%S')}] ESP32 → Chờ data sensor...")

    # ── 1. Cập nhật sensor data ──
    if has_valid:
        sensor_data = {
            "air_temperature": data.get("airTemp"),
            "air_humidity": data.get("airHumi"),
            "soil_temperature": data.get("soilTemp"),
            "soil_moisture": data.get("soilHumi"),
            "salinity": data.get("salinity"),
            "ec": data.get("ec"),
            "nitrogen": data.get("nitrogen"),
            "phosphorus": data.get("phosphorus"),
            "potassium": data.get("potassium"),
            "soil_ph": data.get("ph"),
            "timestamp": datetime.now().isoformat(),
        }
        latest_data = sensor_data
        await manager.broadcast(sensor_data)

        # ★ Gửi cảnh báo Zalo nếu thông số vượt mức
        try:
            await asyncio.to_thread(check_and_send_zalo_alerts, sensor_data)
        except Exception as e:
            print(f"⚠️ Lỗi check alert: {e}")
    # ── 2. Cập nhật relay states từ ESP32 ──
    # ★ CHỈ cập nhật nếu KHÔNG có lệnh relay đang chờ từ web
    relay_keys = ["heater", "fan", "pump", "mist", "light"]
    has_pending_relay = any(k in esp32_pending_commands for k in relay_keys)
    if not has_pending_relay:
        relay_states["heater"] = bool(data.get("heater", False))
        relay_states["fan"] = bool(data.get("fan", False))
        relay_states["pump"] = bool(data.get("pump", False))
        relay_states["mist"] = bool(data.get("mist", False))
        relay_states["light"] = bool(data.get("light", False))
    await manager.broadcast({"type": "relay_states", "states": relay_states})

    # ── 3. Cập nhật mode từ ESP32 ──
    # ★ CHỈ cập nhật nếu KHÔNG có lệnh mode đang chờ từ web
    if "mode" not in esp32_pending_commands:
        auto_mode = (mode_str == "AUTO")
    await manager.broadcast({"type": "auto_mode", "enabled": auto_mode})

    # ── 4. Cập nhật thresholds từ ESP32 ──
    # ★ CHỈ cập nhật nếu KHÔNG có lệnh settings đang chờ từ web
    threshold_keys = ["tempLow", "tempHigh", "airHumiLow", "airHumiHigh", "soilHumiLow", "soilHumiHigh"]
    has_pending_thresholds = any(k in esp32_pending_commands for k in threshold_keys)
    if data.get("tempLow") is not None and not has_pending_thresholds:
        auto_thresholds["temp_low"] = data.get("tempLow", 20.0)
        auto_thresholds["temp_high"] = data.get("tempHigh", 30.0)
        auto_thresholds["air_humi_low"] = data.get("airHumiLow", 60.0)
        auto_thresholds["air_humi_high"] = data.get("airHumiHigh", 80.0)
        auto_thresholds["soil_humi_low"] = data.get("soilHumiLow", 30.0)
        auto_thresholds["soil_humi_high"] = data.get("soilHumiHigh", 60.0)

    # ── 5. Lưu device info ──
    esp32_device_info = {
        "device_id": device_id,
        "ip": esp_ip,
        "wifi_rssi": rssi,
        "mode": mode_str,
        "last_seen": datetime.now().isoformat(),
    }

    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/esp32/command")
async def esp32_get_command(device_id: str = "esp32_gateway_01"):
    """
    ★ ESP32 poll endpoint này mỗi 1 giây để lấy lệnh từ web.
    Trả về JSON object với các field tùy chọn:
      - mode: "AUTO" | "MANUAL"
      - heater/fan/pump/mist/light: true/false (chỉ áp dụng khi MANUAL)
      - tempLow/tempHigh/airHumiLow/.../soilHumiHigh: float (cập nhật ngưỡng)
    Trả rỗng {} nếu không có lệnh.
    """
    global esp32_pending_commands

    if not esp32_pending_commands:
        return {}

    # Lấy và xóa queue
    commands = dict(esp32_pending_commands)
    esp32_pending_commands = {}

    print(f"📤 Gửi command cho ESP32: {commands}")
    return commands


@app.get("/api/esp32/info")
async def get_esp32_info():
    """Thông tin ESP32 device (IP, WiFi RSSI, last seen, v.v.)."""
    return esp32_device_info if esp32_device_info else {"status": "no_device"}


# ═══════════════════════════════════════════════════════════════════
# Legacy Endpoints (vẫn hoạt động cho serial_bridge + test_send_data)
# ═══════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"status": "online", "message": "Sensor Monitoring API v3.0 (WiFi Direct)"}


@app.post("/api/sensor-data")
async def receive_sensor_data(data: SensorData):
    """Legacy: serial_bridge hoặc test_send_data gửi data qua đây."""
    global latest_data

    timestamp = datetime.now().isoformat()
    data_dict = data.model_dump()
    data_dict["timestamp"] = timestamp
    latest_data = data_dict

    await manager.broadcast(data_dict)
    return {"status": "ok", "timestamp": timestamp}


@app.get("/api/sensor-data/latest")
async def get_latest_data():
    if not latest_data:
        return {"status": "no_data", "message": "Chưa có dữ liệu cảm biến"}
    return latest_data


# ─── Auto Control Endpoints ──────────────────────────────────────

@app.get("/api/auto/status")
async def get_auto_status():
    return {
        "enabled": auto_mode,
        "thresholds": auto_thresholds,
        "log": auto_control_log[-20:],
    }


@app.post("/api/auto/toggle")
async def toggle_auto_mode():
    """Toggle auto/manual. ★ Queue lệnh MODE cho ESP32."""
    global auto_mode
    auto_mode = not auto_mode

    await manager.broadcast({"type": "auto_mode", "enabled": auto_mode})

    # ★ Queue cho ESP32 WiFi polling
    esp32_pending_commands["mode"] = "AUTO" if auto_mode else "MANUAL"

    # Legacy: queue cho serial_bridge
    relay_command_queue.append({
        "type": "mode_command",
        "mode": "AUTO" if auto_mode else "MANUAL",
    })

    return {"enabled": auto_mode}


class AutoThresholds(BaseModel):
    temp_low: Optional[float] = None
    temp_high: Optional[float] = None
    air_humi_low: Optional[float] = None
    air_humi_high: Optional[float] = None
    soil_humi_low: Optional[float] = None
    soil_humi_high: Optional[float] = None


@app.post("/api/auto/thresholds")
async def update_thresholds(t: AutoThresholds):
    """Cập nhật ngưỡng tự động. ★ Queue cho ESP32."""
    updates = t.model_dump(exclude_none=True)
    auto_thresholds.update(updates)

    # ★ Queue cho ESP32 WiFi polling (dùng key name ESP32 hiểu)
    key_map = {
        "temp_low": "tempLow",
        "temp_high": "tempHigh",
        "air_humi_low": "airHumiLow",
        "air_humi_high": "airHumiHigh",
        "soil_humi_low": "soilHumiLow",
        "soil_humi_high": "soilHumiHigh",
    }
    for api_key, esp_key in key_map.items():
        if api_key in updates:
            esp32_pending_commands[esp_key] = updates[api_key]

    # Legacy: queue cho serial_bridge
    relay_command_queue.append({
        "type": "settings_command",
        "thresholds": dict(auto_thresholds),
    })

    return auto_thresholds


# ─── Relay Control ───────────────────────────────────────────────

@app.get("/api/relay/status")
async def get_relay_status():
    return relay_states


@app.post("/api/relay/control")
async def control_relay(cmd: RelayCommand):
    """Toggle relay. ★ Queue cho ESP32. ESP32 quyết định cuối cùng."""
    valid_relays = ["heater", "fan", "pump", "mist", "light"]
    if cmd.relay not in valid_relays:
        raise HTTPException(status_code=400, detail=f"Invalid relay: {cmd.relay}")

    # Optimistic update trên backend
    relay_states[cmd.relay] = cmd.state

    await manager.broadcast({"type": "relay_states", "states": relay_states})

    # ★ Queue cho ESP32 WiFi polling
    esp32_pending_commands[cmd.relay] = cmd.state

    # Legacy: queue cho serial_bridge
    relay_command_queue.append({
        "type": "relay_command",
        "relay": cmd.relay,
        "state": cmd.state,
    })

    return {"status": "ok", "relay": cmd.relay, "state": cmd.state}


@app.get("/api/relay/pending")
async def get_pending_commands():
    """Legacy: serial_bridge polls endpoint này."""
    global relay_command_queue
    commands = list(relay_command_queue)
    relay_command_queue = []
    return commands


@app.post("/api/relay/sync-from-device")
async def sync_relay_from_device(states: dict):
    """Legacy: serial_bridge gửi relay state từ ESP32."""
    valid_relays = ["heater", "fan", "pump", "mist", "light"]
    for key, val in states.items():
        if key in valid_relays:
            relay_states[key] = bool(val)
    await manager.broadcast({"type": "relay_states", "states": relay_states})
    return relay_states


# ─── Mode Sync (legacy) ─────────────────────────────────────────

class ModeSyncRequest(BaseModel):
    mode: str


@app.post("/api/mode/sync-from-device")
async def sync_mode_from_device(req: ModeSyncRequest):
    """Legacy: serial_bridge gửi mode từ ESP32."""
    global auto_mode
    mode_upper = req.mode.upper()
    if mode_upper not in ("AUTO", "MANUAL"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")
    auto_mode = (mode_upper == "AUTO")
    await manager.broadcast({"type": "auto_mode", "enabled": auto_mode})
    return {"enabled": auto_mode, "mode": mode_upper}


# ─── Zalo Config ─────────────────────────────────────────────────

class ZaloConfigRequest(BaseModel):
    bot_token: str
    chat_id: str
    send_interval: Optional[int] = None

@app.get("/api/zalo/config")
async def get_zalo_config_endpoint():
    return {
        "bot_token": zalo_config.get("bot_token", ""),
        "chat_id": zalo_config.get("chat_id", ""),
        "auto_send": zalo_auto_send,
        "send_interval": zalo_send_interval
    }

@app.post("/api/zalo/config")
async def save_zalo_config_endpoint(req: ZaloConfigRequest):
    global zalo_config, zalo_send_interval
    interval = req.send_interval if req.send_interval and req.send_interval >= 10 else zalo_send_interval
    if save_zalo_config(req.bot_token, req.chat_id, interval):
        zalo_config["bot_token"] = req.bot_token
        zalo_config["chat_id"] = req.chat_id
        zalo_config["send_interval"] = interval
        zalo_send_interval = interval
        return {"status": "ok", "message": "Đã lưu cấu hình Zalo thành công"}
    else:
        raise HTTPException(status_code=500, detail="Không thể lưu file cấu hình Zalo")

class ZaloFetchIdRequest(BaseModel):
    bot_token: str

@app.post("/api/zalo/fetch-id")
async def fetch_zalo_chat_id(req: ZaloFetchIdRequest):
    chat_id, error = await asyncio.to_thread(fetch_chat_id_from_updates, req.bot_token)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"chat_id": chat_id, "message": "Lấy Chat ID thành công!"}

class ZaloToggleRequest(BaseModel):
    auto_send: bool

@app.post("/api/zalo/toggle")
async def toggle_zalo_auto_send(req: ZaloToggleRequest):
    global zalo_auto_send
    zalo_auto_send = req.auto_send
    return {"status": "ok", "auto_send": zalo_auto_send}


# ─── AI Analysis ─────────────────────────────────────────────────

@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_data(request: AnalysisRequest):
    data = request.sensor_data.model_dump() if request.sensor_data else latest_data

    if not data:
        raise HTTPException(status_code=400, detail="Không có dữ liệu để phân tích")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        analysis_text = _generate_mock_analysis(data)
        return AnalysisResponse(
            analysis=analysis_text,
            timestamp=datetime.now().isoformat()
        )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt = f"""Bạn là chuyên gia nông nghiệp thông minh. Dựa trên dữ liệu cảm biến sau đây, hãy phân tích tình trạng đất và môi trường, sau đó đưa ra khuyến nghị cụ thể cho nông dân.

DỮ LIỆU CẢM BIẾN:
- Nhiệt độ đất: {data.get('soil_temperature', 'N/A')}°C
- Độ ẩm đất: {data.get('soil_moisture', 'N/A')}%
- pH đất: {data.get('soil_ph', 'N/A')}
- EC (Độ dẫn điện): {data.get('ec', 'N/A')} µS/cm
- Nitrogen (N): {data.get('nitrogen', 'N/A')} mg/kg
- Phosphorus (P): {data.get('phosphorus', 'N/A')} mg/kg
- Potassium (K): {data.get('potassium', 'N/A')} mg/kg
- Độ mặn: {data.get('salinity', 'N/A')} mg/L
- Nhiệt độ không khí: {data.get('air_temperature', 'N/A')}°C
- Độ ẩm không khí: {data.get('air_humidity', 'N/A')}%

Hãy trả lời bằng tiếng Việt với format:
1. 📊 ĐÁNH GIÁ TỔNG QUAN (tốt/trung bình/cần cải thiện)
2. ⚠️ CÁC CHỈ SỐ CẦN LƯU Ý (nếu có)
3. 💡 KHUYẾN NGHỊ CỤ THỂ (nên làm gì tiếp theo)
4. 🌱 GỢI Ý CÂY TRỒNG PHÙ HỢP (dựa trên điều kiện hiện tại)
"""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.0-flash",
            contents=prompt,
        )
        analysis_text = response.text

    except Exception as e:
        analysis_text = f"⚠️ Lỗi khi phân tích: {str(e)}\n\n" + _generate_mock_analysis(data)

    return AnalysisResponse(
        analysis=analysis_text,
        timestamp=datetime.now().isoformat()
    )


def _generate_mock_analysis(data: dict) -> str:
    warnings = []
    suggestions = []

    ph = data.get("soil_ph")
    if ph is not None:
        if ph < 5.5:
            warnings.append("⚠️ pH đất quá thấp (acid)")
            suggestions.append("Bón vôi để tăng pH đất")
        elif ph > 7.5:
            warnings.append("⚠️ pH đất quá cao (kiềm)")
            suggestions.append("Bón lưu huỳnh hoặc phân hữu cơ để giảm pH")
        else:
            suggestions.append("✅ pH đất ở mức tốt")

    moisture = data.get("soil_moisture")
    if moisture is not None:
        if moisture < 20:
            warnings.append("⚠️ Độ ẩm đất quá thấp")
            suggestions.append("Cần tưới nước thêm cho đất")
        elif moisture > 80:
            warnings.append("⚠️ Độ ẩm đất quá cao")
            suggestions.append("Giảm tưới, kiểm tra hệ thống thoát nước")

    temp = data.get("air_temperature")
    if temp is not None:
        if temp > 35:
            warnings.append("⚠️ Nhiệt độ không khí cao")
            suggestions.append("Che phủ đất, tưới vào sáng sớm/chiều tối")
        elif temp < 15:
            warnings.append("⚠️ Nhiệt độ không khí thấp")
            suggestions.append("Phủ ni-lông giữ ấm cho cây")

    n = data.get("nitrogen")
    if n is not None and n < 20:
        warnings.append("⚠️ Nitrogen thấp")
        suggestions.append("Bón phân đạm (Ure, NPK)")

    result = "📊 **ĐÁNH GIÁ TỔNG QUAN**\n\n"
    if len(warnings) == 0:
        result += "✅ Tất cả chỉ số trong mức bình thường.\n\n"
    else:
        result += f"Có {len(warnings)} chỉ số cần lưu ý.\n\n"
        result += "⚠️ **CÁC CHỈ SỐ CẦN LƯU Ý**\n"
        for w in warnings:
            result += f"- {w}\n"
        result += "\n"

    result += "💡 **KHUYẾN NGHỊ**\n"
    for s in suggestions:
        result += f"- {s}\n"

    result += "\n_⚡ Đây là phân tích cơ bản. Thêm GEMINI_API_KEY vào file .env để có phân tích AI chi tiết hơn._"
    return result


# ─── WebSocket ───────────────────────────────────────────────────

@app.websocket("/ws/sensor-data")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Gửi state hiện tại ngay khi connect
        if latest_data:
            await websocket.send_json(latest_data)
        await websocket.send_json({"type": "auto_mode", "enabled": auto_mode})
        await websocket.send_json({"type": "relay_states", "states": relay_states})

        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

# ═══════════════════════════════════════════════════════════════════
# ★ AI Analysis - Google Gemini
# ═══════════════════════════════════════════════════════════════════

GEMINI_API_KEY = "AIzaSyCcPsz1skt_lIISiJopzCrh68rqKjFprpM"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

@app.post("/api/analysis")
async def ai_analysis(data: dict):
    """Phân tích dữ liệu cảm biến bằng Google Gemini AI."""
    import httpx

    sensor = data.get("sensor_data", {})

    prompt = f"""Bạn là chuyên gia nông nghiệp thông minh. Phân tích dữ liệu cảm biến nhà kính sau và đưa ra đánh giá + khuyến nghị ngắn gọn bằng tiếng Việt:

📊 Dữ liệu:
- Nhiệt độ không khí: {sensor.get('air_temperature', 'N/A')}°C
- Độ ẩm không khí: {sensor.get('air_humidity', 'N/A')}%
- Nhiệt độ đất: {sensor.get('soil_temperature', 'N/A')}°C
- Độ ẩm đất: {sensor.get('soil_moisture', 'N/A')}%
- pH đất: {sensor.get('soil_ph', 'N/A')}
- EC (độ dẫn điện): {sensor.get('ec', 'N/A')} µS/cm
- Độ mặn: {sensor.get('salinity', 'N/A')}
- Nitrogen (N): {sensor.get('nitrogen', 'N/A')} mg/kg
- Phosphorus (P): {sensor.get('phosphorus', 'N/A')} mg/kg
- Potassium (K): {sensor.get('potassium', 'N/A')} mg/kg

Trả lời theo format:
🌡️ ĐÁNH GIÁ TỔNG QUAN: (1-2 câu)
⚠️ CẢNH BÁO: (nếu có thông số bất thường)
💡 KHUYẾN NGHỊ: (3-5 gợi ý cụ thể)
🌱 ĐÁNH GIÁ CÂY TRỒNG: (phù hợp trồng gì)
"""

    gemini_payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1000,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(GEMINI_URL, json=gemini_payload)

        if res.status_code != 200:
            print(f"❌ Gemini API error: {res.status_code} - {res.text[:200]}")
            raise HTTPException(status_code=500, detail=f"Gemini API error: {res.status_code}")

        result = res.json()
        text = result["candidates"][0]["content"]["parts"][0]["text"]

        print(f"🤖 AI Analysis done: {len(text)} chars")

        return {
            "analysis": text,
            "timestamp": datetime.now().isoformat(),
            "model": "gemini-2.0-flash"
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini API timeout")
    except Exception as e:
        print(f"❌ AI Analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
