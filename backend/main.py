"""
FastAPI Backend - Real-time Sensor Monitoring & AI Analysis
No database - in-memory latest values + WebSocket broadcast
"""

import os
import json
import asyncio
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
    sensor_data: Optional[SensorData] = None  # If None, use latest


class AnalysisResponse(BaseModel):
    analysis: str
    timestamp: str


class RelayCommand(BaseModel):
    relay: str  # heater, fan, pump, mist, light
    state: bool  # True = ON, False = OFF


# ─── WebSocket Manager ───────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


# ─── App Setup ───────────────────────────────────────────────────

app = FastAPI(
    title="Sensor Monitoring API",
    description="Real-time agricultural sensor monitoring with AI analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()

# In-memory storage for latest sensor data
latest_data: dict = {}

# In-memory relay states
relay_states: dict = {
    "heater": False,
    "fan": False,
    "pump": False,
    "mist": False,
    "light": False,
}

# Queue for relay commands to send to ESP32 via serial bridge
relay_command_queue: list = []

# ─── Auto Control ────────────────────────────────────────────────

auto_mode: bool = False

auto_thresholds: dict = {
    # Nhiệt độ không khí → Sưởi / Quạt
    "temp_low": 20.0,       # Dưới → bật Sưởi
    "temp_high": 30.0,      # Trên → bật Quạt
    # Độ ẩm không khí → Phun sương
    "air_humi_low": 60.0,   # Dưới → bật Phun sương
    "air_humi_high": 80.0,  # Trên → tắt Phun sương
    # Độ ẩm đất → Bơm
    "soil_humi_low": 30.0,  # Dưới → bật Bơm
    "soil_humi_high": 60.0, # Trên → tắt Bơm
    # Ánh sáng → Đèn
    "light_low": 5000.0,    # Dưới → bật Đèn
    "light_high": 30000.0,  # Trên → tắt Đèn
}

auto_control_log: list = []  # Recent auto actions

# ─── Zalo Settings ───────────────────────────────────────────────
zalo_config = load_zalo_config()

# Cờ để kiểm soát việc gửi tự động
zalo_auto_send: bool = True  # Mặc định bật
zalo_send_interval: int = zalo_config.get("send_interval", 30)  # Giây

# ─── Zalo Background Task ────────────────────────────────────────

async def zalo_periodic_task():
    """Gửi dữ liệu lên Zalo định kỳ theo khoảng thời gian cấu hình."""
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
            print(f"⚠️ Lỗi trong zalo_periodic_task: {e}")

@app.on_event("startup")
async def startup_event():
    # Khởi chạy Zalo task ngầm
    asyncio.create_task(zalo_periodic_task())


async def auto_control_check(data: dict):
    """Tự động bật/tắt relay dựa trên ngưỡng cảm biến."""
    global relay_states, auto_control_log
    if not auto_mode:
        return

    changes = []

    # Nhiệt độ → Sưởi / Quạt
    air_temp = data.get("air_temperature")
    if air_temp is not None:
        if air_temp < auto_thresholds["temp_low"]:
            if not relay_states["heater"]:
                relay_states["heater"] = True
                changes.append({"relay": "heater", "state": True, "reason": f"Nhiệt độ thấp ({air_temp}°C < {auto_thresholds['temp_low']}°C)"})
            if relay_states["fan"]:
                relay_states["fan"] = False
                changes.append({"relay": "fan", "state": False, "reason": f"Tắt quạt vì đang lạnh"})
        elif air_temp > auto_thresholds["temp_high"]:
            if not relay_states["fan"]:
                relay_states["fan"] = True
                changes.append({"relay": "fan", "state": True, "reason": f"Nhiệt độ cao ({air_temp}°C > {auto_thresholds['temp_high']}°C)"})
            if relay_states["heater"]:
                relay_states["heater"] = False
                changes.append({"relay": "heater", "state": False, "reason": f"Tắt sưởi vì đang nóng"})
        else:
            # Trong ngưỡng → tắt cả hai
            if relay_states["heater"]:
                relay_states["heater"] = False
                changes.append({"relay": "heater", "state": False, "reason": f"Nhiệt độ bình thường ({air_temp}°C)"})
            if relay_states["fan"]:
                relay_states["fan"] = False
                changes.append({"relay": "fan", "state": False, "reason": f"Nhiệt độ bình thường ({air_temp}°C)"})

    # Độ ẩm không khí → Phun sương
    air_humi = data.get("air_humidity")
    if air_humi is not None:
        if air_humi < auto_thresholds["air_humi_low"]:
            if not relay_states["mist"]:
                relay_states["mist"] = True
                changes.append({"relay": "mist", "state": True, "reason": f"Độ ẩm KK thấp ({air_humi}% < {auto_thresholds['air_humi_low']}%)"})
        elif air_humi > auto_thresholds["air_humi_high"]:
            if relay_states["mist"]:
                relay_states["mist"] = False
                changes.append({"relay": "mist", "state": False, "reason": f"Độ ẩm KK cao ({air_humi}% > {auto_thresholds['air_humi_high']}%)"})

    # Độ ẩm đất → Bơm
    soil_humi = data.get("soil_moisture")
    if soil_humi is not None:
        if soil_humi < auto_thresholds["soil_humi_low"]:
            if not relay_states["pump"]:
                relay_states["pump"] = True
                changes.append({"relay": "pump", "state": True, "reason": f"Đất khô ({soil_humi}% < {auto_thresholds['soil_humi_low']}%)"})
        elif soil_humi > auto_thresholds["soil_humi_high"]:
            if relay_states["pump"]:
                relay_states["pump"] = False
                changes.append({"relay": "pump", "state": False, "reason": f"Đất đủ ẩm ({soil_humi}% > {auto_thresholds['soil_humi_high']}%)"})

    # Ánh sáng → Đèn
    light = data.get("light_intensity")
    if light is not None:
        if light < auto_thresholds["light_low"]:
            if not relay_states["light"]:
                relay_states["light"] = True
                changes.append({"relay": "light", "state": True, "reason": f"Thiếu sáng ({light} lux < {auto_thresholds['light_low']} lux)"})
        elif light > auto_thresholds["light_high"]:
            if relay_states["light"]:
                relay_states["light"] = False
                changes.append({"relay": "light", "state": False, "reason": f"Đủ sáng ({light} lux > {auto_thresholds['light_high']} lux)"})

    # Broadcast changes
    for change in changes:
        command_msg = {
            "type": "relay_command",
            "relay": change["relay"],
            "state": change["state"],
        }
        await manager.broadcast(command_msg)
        relay_command_queue.append(command_msg)

        # Log
        log_entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "relay": change["relay"],
            "state": change["state"],
            "reason": change["reason"],
        }
        auto_control_log.append(log_entry)
        # Giữ tối đa 50 log
        if len(auto_control_log) > 50:
            auto_control_log.pop(0)

    # Broadcast relay states update
    if changes:
        await manager.broadcast({"type": "relay_update", "states": relay_states})


# ─── REST Endpoints ──────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "online", "message": "Sensor Monitoring API v1.0"}


@app.post("/api/sensor-data")
async def receive_sensor_data(data: SensorData):
    """
    ESP32 pushes sensor readings here.
    Data is stored in-memory and broadcast to all WebSocket clients.
    """
    global latest_data

    timestamp = datetime.now().isoformat()
    data_dict = data.model_dump()
    data_dict["timestamp"] = timestamp

    latest_data = data_dict

    # Broadcast to all connected WebSocket clients
    await manager.broadcast(data_dict)

    # Auto-control check
    await auto_control_check(data_dict)

    return {"status": "ok", "timestamp": timestamp}


@app.get("/api/sensor-data/latest")
async def get_latest_data():
    """Get the most recent sensor reading."""
    if not latest_data:
        return {"status": "no_data", "message": "Chưa có dữ liệu cảm biến"}
    return latest_data


# ─── Auto Control Endpoints ──────────────────────────────────────

@app.get("/api/auto/status")
async def get_auto_status():
    """Get auto-control mode status, thresholds, and recent log."""
    return {
        "enabled": auto_mode,
        "thresholds": auto_thresholds,
        "log": auto_control_log[-20:],  # Last 20 entries
    }


@app.post("/api/auto/toggle")
async def toggle_auto_mode():
    """Toggle auto-control mode on/off."""
    global auto_mode
    auto_mode = not auto_mode
    # Broadcast mode change
    await manager.broadcast({"type": "auto_mode", "enabled": auto_mode})
    # Chạy auto-control ngay với data hiện tại khi bật
    if auto_mode and latest_data:
        await auto_control_check(latest_data)
    return {"enabled": auto_mode}


class AutoThresholds(BaseModel):
    temp_low: Optional[float] = None
    temp_high: Optional[float] = None
    air_humi_low: Optional[float] = None
    air_humi_high: Optional[float] = None
    soil_humi_low: Optional[float] = None
    soil_humi_high: Optional[float] = None
    light_low: Optional[float] = None
    light_high: Optional[float] = None


@app.post("/api/auto/thresholds")
async def update_thresholds(t: AutoThresholds):
    """Update auto-control thresholds."""
    updates = t.model_dump(exclude_none=True)
    auto_thresholds.update(updates)
    # Chạy auto-control ngay với ngưỡng mới
    if auto_mode and latest_data:
        await auto_control_check(latest_data)
    # ★ Queue settings command để serial bridge gửi xuống ESP32
    relay_command_queue.append({
        "type": "settings_command",
        "thresholds": dict(auto_thresholds),
    })
    return auto_thresholds


# ─── Relay Control ───────────────────────────────────────────────

@app.get("/api/relay/status")
async def get_relay_status():
    """Get current relay states."""
    return relay_states


@app.post("/api/relay/control")
async def control_relay(cmd: RelayCommand):
    """Toggle a relay on/off. Broadcasts to serial bridge via WS."""
    valid_relays = ["heater", "fan", "pump", "mist", "light"]
    if cmd.relay not in valid_relays:
        raise HTTPException(status_code=400, detail=f"Invalid relay: {cmd.relay}. Must be one of {valid_relays}")

    relay_states[cmd.relay] = cmd.state

    # Broadcast relay command to all WS clients (including serial bridge)
    command_msg = {
        "type": "relay_command",
        "relay": cmd.relay,
        "state": cmd.state,
    }
    await manager.broadcast(command_msg)

    # Also queue for serial bridge polling
    relay_command_queue.append(command_msg)

    return {"status": "ok", "relay": cmd.relay, "state": cmd.state}


@app.get("/api/relay/pending")
async def get_pending_commands():
    """Serial bridge polls this to get pending relay commands."""
    global relay_command_queue
    commands = list(relay_command_queue)
    relay_command_queue = []
    return commands


@app.post("/api/relay/sync-from-device")
async def sync_relay_from_device(states: dict):
    """★ ESP32 gửi trạng thái relay lên (qua serial_bridge) → cập nhật web."""
    valid_relays = ["heater", "fan", "pump", "mist", "light"]
    for key, val in states.items():
        if key in valid_relays:
            relay_states[key] = bool(val)

    # Broadcast relay states to all WS clients → frontend cập nhật ngay
    await manager.broadcast({
        "type": "relay_states",
        "states": relay_states,
    })
    return relay_states


# ─── Zalo Config Endpoints ───────────────────────────────────────

class ZaloConfigRequest(BaseModel):
    bot_token: str
    chat_id: str
    send_interval: Optional[int] = None  # Giây, nếu None giữ nguyên

@app.get("/api/zalo/config")
async def get_zalo_config_endpoint():
    """Lấy cấu hình Zalo hiện tại"""
    return {
        "bot_token": zalo_config.get("bot_token", ""),
        "chat_id": zalo_config.get("chat_id", ""),
        "auto_send": zalo_auto_send,
        "send_interval": zalo_send_interval
    }

@app.post("/api/zalo/config")
async def save_zalo_config_endpoint(req: ZaloConfigRequest):
    """Lưu cấu hình Zalo"""
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
    """Lấy Chat ID tự động dựa trên Token"""
    chat_id, error = await asyncio.to_thread(fetch_chat_id_from_updates, req.bot_token)
    if error:
        raise HTTPException(status_code=400, detail=error)
    return {"chat_id": chat_id, "message": "Lấy Chat ID thành công!"}

class ZaloToggleRequest(BaseModel):
    auto_send: bool

@app.post("/api/zalo/toggle")
async def toggle_zalo_auto_send(req: ZaloToggleRequest):
    """Bật/tắt việc gửi tự động Zalo"""
    global zalo_auto_send
    zalo_auto_send = req.auto_send
    return {"status": "ok", "auto_send": zalo_auto_send}


# ─── AI Analysis ─────────────────────────────────────────────────

@app.post("/api/analysis", response_model=AnalysisResponse)
async def analyze_data(request: AnalysisRequest):
    """
    Use Google Gemini to analyze sensor data and provide recommendations.
    """
    data = request.sensor_data.model_dump() if request.sensor_data else latest_data

    if not data:
        raise HTTPException(status_code=400, detail="Không có dữ liệu để phân tích")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_api_key_here":
        # Return mock analysis if no API key
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
- Cường độ ánh sáng: {data.get('light_intensity', 'N/A')} lux

Hãy trả lời bằng tiếng Việt với format:
1. 📊 ĐÁNH GIÁ TỔNG QUAN (tốt/trung bình/cần cải thiện)
2. ⚠️ CÁC CHỈ SỐ CẦN LƯU Ý (nếu có)
3. 💡 KHUYẾN NGHỊ CỤ THỂ (nên làm gì tiếp theo)
4. 🌱 GỢI Ý CÂY TRỒNG PHÙ HỢP (dựa trên điều kiện hiện tại)
"""

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3-flash-preview",
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
    """Generate a basic analysis when Gemini API is not available."""
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
        # Send latest data immediately on connect
        if latest_data:
            await websocket.send_json(latest_data)

        # Keep connection alive, listen for client messages
        while True:
            try:
                # Wait for any message from client (ping/pong keepalive)
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send ping to keep alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


# ─── Run ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
