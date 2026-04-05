"""
Serial Bridge v7 — Python version của ESP32 Gateway firmware
Chuyển từ C++ sang Python, chạy trên máy tính thay ESP32.
Kết nối WiFi HTTP trực tiếp đến backend (giống ESP32 thật).

Chức năng:
  1. Upload data lên backend mỗi 3 giây (POST /api/esp32/upload)
  2. Fetch commands từ backend mỗi 1 giây (GET /api/esp32/command)
  3. Xử lý lệnh: MODE (AUTO/MANUAL), relay, settings
  4. Hiển thị trạng thái trên terminal (thay LCD)
  5. Mô phỏng sensor data (random trong khoảng thực tế)

Cách dùng:
  python serial_bridge.py
"""
import requests
import time
import random
import threading
import os
import json
import socket

# ════════════════ WIFI CONFIG (giống C++) ════════════════
# Backend URL — đổi IP nếu backend chạy trên máy khác
API_URL = "http://localhost:8000"

UPLOAD_ENDPOINT = "/api/esp32/upload"
COMMAND_ENDPOINT = "/api/esp32/command"

# ════════════════ TIMING (giống C++) ════════════════
UPLOAD_INTERVAL = 3.0    # Upload mỗi 3 giây
FETCH_CMD_INTERVAL = 1.0  # Fetch command mỗi 1 giây
NODE_TIMEOUT = 15.0       # Node timeout 15 giây

# ════════════════ DATA STRUCT (giống C++) ════════════════
class SensorData:
    def __init__(self):
        self.airTemp = 0.0
        self.airHumi = 0.0
        self.soilTemp = 0.0
        self.soilHumi = 0.0
        self.salinity = 0
        self.ec = 0
        self.nitrogen = 0
        self.phosphorus = 0
        self.potassium = 0
        self.ph = 0.0

class Settings:
    def __init__(self):
        self.tempLow = 20.0
        self.tempHigh = 30.0
        self.airHumiLow = 60.0
        self.airHumiHigh = 80.0
        self.soilHumiLow = 30.0
        self.soilHumiHigh = 60.0

# ════════════════ STATE (giống C++) ════════════════
currentData = SensorData()
cfg = Settings()
hasValidData = False

# Relay states
heaterState = False
fanState = False
pumpState = False
mistState = False
lightState = False

# Control mode
MODE_AUTO = 0
MODE_MANUAL = 1
controlMode = MODE_AUTO

# Device info
DEVICE_ID = "esp32_gateway_01"

# Upload count
uploadCount = 0

# ════════════════ UTIL (giống C++) ════════════════
def modeToString():
    return "AUTO" if controlMode == MODE_AUTO else "MANUAL"

def get_local_ip():
    """Lấy IP máy tính trên mạng LAN."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def validateSettings(s):
    """Validate settings (giống C++)."""
    s.tempLow = max(0.0, min(s.tempLow, 79.5))
    s.tempHigh = max(0.5, min(s.tempHigh, 80.0))
    s.airHumiLow = max(0.0, min(s.airHumiLow, 99.0))
    s.airHumiHigh = max(1.0, min(s.airHumiHigh, 100.0))
    s.soilHumiLow = max(0.0, min(s.soilHumiLow, 99.0))
    s.soilHumiHigh = max(1.0, min(s.soilHumiHigh, 100.0))

    if s.tempLow >= s.tempHigh:
        s.tempLow = 20.0
        s.tempHigh = 30.0
    if s.airHumiLow >= s.airHumiHigh:
        s.airHumiLow = 60.0
        s.airHumiHigh = 80.0
    if s.soilHumiLow >= s.soilHumiHigh:
        s.soilHumiLow = 30.0
        s.soilHumiHigh = 60.0

# ════════════════ SIMULATE SENSOR (thay LoRa) ════════════════
def generateSensorData():
    """Mô phỏng data cảm biến (thay thế LoRa receiver)."""
    global hasValidData
    currentData.airTemp = round(random.uniform(20.0, 35.0), 1)
    currentData.airHumi = round(random.uniform(40.0, 90.0), 1)
    currentData.soilTemp = round(random.uniform(18.0, 30.0), 1)
    currentData.soilHumi = round(random.uniform(20.0, 80.0), 1)
    currentData.salinity = random.randint(100, 500)
    currentData.ec = random.randint(200, 1500)
    currentData.nitrogen = random.randint(10, 100)
    currentData.phosphorus = random.randint(5, 50)
    currentData.potassium = random.randint(50, 200)
    currentData.ph = round(random.uniform(5.0, 8.0), 1)
    hasValidData = True

# ════════════════ AUTO CONTROL (giống C++) ════════════════
def controlOutputsAuto():
    """Điều khiển tự động dựa trên ngưỡng (giống C++)."""
    global heaterState, fanState, pumpState, mistState

    if controlMode != MODE_AUTO:
        return

    # Nhiệt độ → Sưởi / Quạt
    if currentData.airTemp < cfg.tempLow:
        heaterState = True
        fanState = False
    elif currentData.airTemp > cfg.tempHigh:
        heaterState = False
        fanState = True
    else:
        heaterState = False
        fanState = False

    # Độ ẩm KK → Phun sương
    if currentData.airHumi < cfg.airHumiLow:
        mistState = True
    elif currentData.airHumi > cfg.airHumiHigh:
        mistState = False

    # Độ ẩm đất → Bơm
    if currentData.soilHumi < cfg.soilHumiLow:
        pumpState = True
    elif currentData.soilHumi > cfg.soilHumiHigh:
        pumpState = False

# ════════════════ HTTP: UPLOAD (giống C++ uploadDataToServer) ════════════════
def uploadDataToServer():
    """POST toàn bộ state lên backend (giống ESP32)."""
    global uploadCount

    payload = {
        "device_id": DEVICE_ID,
        "hasValidData": hasValidData,
        "mode": modeToString(),

        # Sensor data
        "airTemp": currentData.airTemp,
        "airHumi": currentData.airHumi,
        "soilTemp": currentData.soilTemp,
        "soilHumi": currentData.soilHumi,
        "salinity": currentData.salinity,
        "ec": currentData.ec,
        "nitrogen": currentData.nitrogen,
        "phosphorus": currentData.phosphorus,
        "potassium": currentData.potassium,
        "ph": currentData.ph,

        # Relay states
        "heater": heaterState,
        "fan": fanState,
        "pump": pumpState,
        "mist": mistState,
        "light": lightState,

        # Settings
        "tempLow": cfg.tempLow,
        "tempHigh": cfg.tempHigh,
        "airHumiLow": cfg.airHumiLow,
        "airHumiHigh": cfg.airHumiHigh,
        "soilHumiLow": cfg.soilHumiLow,
        "soilHumiHigh": cfg.soilHumiHigh,

        # WiFi info
        "wifi_rssi": random.randint(-60, -30),
        "ip": get_local_ip(),
    }

    try:
        res = requests.post(f"{API_URL}{UPLOAD_ENDPOINT}", json=payload, timeout=5)
        uploadCount += 1

        if res.status_code == 200:
            return True
        else:
            print(f"   [UPLOAD] HTTP code: {res.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"   [UPLOAD] Không kết nối backend! Kiểm tra: python main.py")
        return False
    except Exception as e:
        print(f"   [UPLOAD] Lỗi: {e}")
        return False

# ════════════════ HTTP: FETCH CMD (giống C++ fetchCommandFromServer) ════════════════
def fetchCommandFromServer():
    """GET lệnh từ backend (giống ESP32)."""
    global controlMode, heaterState, fanState, pumpState, mistState, lightState

    try:
        res = requests.get(
            f"{API_URL}{COMMAND_ENDPOINT}",
            params={"device_id": DEVICE_ID},
            timeout=3
        )

        if res.status_code != 200:
            return

        payload = res.text
        if not payload or payload == "{}":
            return

        cmd = res.json()
        if not cmd:
            return

        print(f"   📥 Nhận lệnh: {json.dumps(cmd, ensure_ascii=False)}")

        # ── Xử lý MODE (giống C++) ──
        if "mode" in cmd:
            mode = cmd["mode"]
            if mode == "AUTO":
                controlMode = MODE_AUTO
                if hasValidData:
                    controlOutputsAuto()
                else:
                    turnOffAllOutputs()
                print(f"   🔄 Chuyển sang AUTO")
            elif mode == "MANUAL":
                controlMode = MODE_MANUAL
                print(f"   🔄 Chuyển sang MANUAL")

        # ── Xử lý Settings (giống C++ applySettingsFromJson) ──
        changed = False
        if "tempLow" in cmd:
            cfg.tempLow = cmd["tempLow"]; changed = True
        if "tempHigh" in cmd:
            cfg.tempHigh = cmd["tempHigh"]; changed = True
        if "airHumiLow" in cmd:
            cfg.airHumiLow = cmd["airHumiLow"]; changed = True
        if "airHumiHigh" in cmd:
            cfg.airHumiHigh = cmd["airHumiHigh"]; changed = True
        if "soilHumiLow" in cmd:
            cfg.soilHumiLow = cmd["soilHumiLow"]; changed = True
        if "soilHumiHigh" in cmd:
            cfg.soilHumiHigh = cmd["soilHumiHigh"]; changed = True

        if changed:
            validateSettings(cfg)
            print(f"   ⚙️ Settings cập nhật: T={cfg.tempLow}-{cfg.tempHigh}°C")

        # ── Xử lý Relay (chỉ khi MANUAL, giống C++) ──
        if controlMode == MODE_MANUAL:
            if "heater" in cmd:
                heaterState = bool(cmd["heater"])
            if "fan" in cmd:
                fanState = bool(cmd["fan"])
            if "pump" in cmd:
                pumpState = bool(cmd["pump"])
            if "mist" in cmd:
                mistState = bool(cmd["mist"])
            if "light" in cmd:
                lightState = bool(cmd["light"])
            print(f"   🎛️ Relay: H={heaterState} F={fanState} P={pumpState} M={mistState} L={lightState}")

    except requests.exceptions.ConnectionError:
        pass
    except Exception as e:
        print(f"   [CMD] Lỗi: {e}")

def turnOffAllOutputs():
    global heaterState, fanState, pumpState, mistState, lightState
    heaterState = False
    fanState = False
    pumpState = False
    mistState = False
    lightState = False

# ════════════════ DISPLAY (thay LCD) ════════════════
def displayStatus():
    """Hiển thị trạng thái trên terminal (thay LCD 20x4)."""
    os.system('cls' if os.name == 'nt' else 'clear')

    mode_str = "AUTO" if controlMode == MODE_AUTO else "MANUAL"
    relay_on = lambda s: f"\033[92mON\033[0m" if s else f"\033[91mOFF\033[0m"

    print("═" * 58)
    print("  🌿 NHÀ KÍNH THÔNG MINH — Python Gateway (thay ESP32)")
    print("═" * 58)
    print()

    # ── Kết nối ──
    print(f"  📡 Device: {DEVICE_ID}")
    print(f"  🌐 IP    : {get_local_ip()}")
    print(f"  🔗 Server: {API_URL}")
    print(f"  📤 Upload: #{uploadCount}  (mỗi {UPLOAD_INTERVAL}s)")
    print()

    print(f"  {'─' * 54}")

    # ── Sensor data ──
    if hasValidData:
        print(f"  📊 \033[1mDỮ LIỆU CẢM BIẾN\033[0m")
        print(f"     🌡️  KK : {currentData.airTemp}°C   💨 Ẩm KK : {currentData.airHumi}%")
        print(f"     🌡️  Đất: {currentData.soilTemp}°C   🌱 Ẩm đất: {currentData.soilHumi}%")
        print(f"     ⚡ EC : {currentData.ec}        🧪 pH    : {currentData.ph}")
        print(f"     🧂 Mặn: {currentData.salinity}        🅽 N={currentData.nitrogen}  🅿 P={currentData.phosphorus}  🅺 K={currentData.potassium}")
    else:
        print(f"  📊 \033[93mChờ dữ liệu cảm biến...\033[0m")

    print()
    print(f"  {'─' * 54}")

    # ── Relay ──
    print(f"  🎛️  \033[1mTHIẾT BỊ\033[0m  ({mode_str})")
    print(f"     🔥 Sưởi: {relay_on(heaterState)}    🌀 Quạt: {relay_on(fanState)}")
    print(f"     💧 Bơm : {relay_on(pumpState)}    🌫️  Phun: {relay_on(mistState)}")
    print(f"     💡 Đèn : {relay_on(lightState)}")

    print()
    print(f"  {'─' * 54}")

    # ── Settings ──
    print(f"  ⚙️  \033[1mNGƯỠNG TỰ ĐỘNG\033[0m")
    print(f"     🌡️  Nhiệt: {cfg.tempLow} - {cfg.tempHigh}°C")
    print(f"     💨 Ẩm KK: {cfg.airHumiLow} - {cfg.airHumiHigh}%")
    print(f"     🌱 Ẩm đất: {cfg.soilHumiLow} - {cfg.soilHumiHigh}%")

    print()
    print("═" * 58)
    print("  Ctrl+C để dừng")

# ════════════════ MAIN LOOP (giống C++ loop()) ════════════════
def main():
    global hasValidData

    print("═" * 58)
    print("  🌿 NHÀ KÍNH THÔNG MINH — Python Gateway")
    print("  📡 Chuyển từ C++ ESP32 sang Python")
    print(f"  🌐 Backend: {API_URL}")
    print(f"  📤 Upload mỗi {UPLOAD_INTERVAL}s")
    print(f"  📥 Fetch cmd mỗi {FETCH_CMD_INTERVAL}s")
    print("═" * 58)
    print()
    print("=== GATEWAY BOOT ===")

    # ── Kiểm tra kết nối backend ──
    print("Đang kết nối backend...", end=" ")
    try:
        res = requests.get(f"{API_URL}/", timeout=5)
        if res.status_code == 200:
            print("=== CONNECTED ===")
            print(f"IP: {get_local_ip()}")
        else:
            print(f"HTTP {res.status_code}")
    except Exception:
        print("=== CONNECT FAILED ===")
        print("Kiểm tra: python main.py đã chạy chưa?")

    time.sleep(1)
    print("=== READY ===\n")

    lastUpload = 0
    lastFetchCmd = 0
    lastSensorUpdate = 0

    try:
        while True:
            now = time.time()

            # ── Mô phỏng nhận data từ LoRa (mỗi 5 giây) ──
            if now - lastSensorUpdate >= 5.0:
                lastSensorUpdate = now
                generateSensorData()

                if controlMode == MODE_AUTO:
                    controlOutputsAuto()

            # ── Upload data (mỗi 3 giây, giống C++) ──
            if now - lastUpload >= UPLOAD_INTERVAL:
                lastUpload = now
                uploadDataToServer()
                displayStatus()

            # ── Fetch commands (mỗi 1 giây, giống C++) ──
            if now - lastFetchCmd >= FETCH_CMD_INTERVAL:
                lastFetchCmd = now
                fetchCommandFromServer()

            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n🛑 Dừng. Upload: {uploadCount} lần.")


if __name__ == "__main__":
    main()
