"""
Serial Bridge v9 — CHỈ MONITOR (KHÔNG GỬI DATA GIẢ)

★ ESP32 thật gửi data qua WiFi → main.py nhận
★ Script này CHỈ ĐỌC từ backend để hiển thị trạng thái
★ KHÔNG tạo data giả, KHÔNG upload lên backend

Luồng data:
  ESP32 (WiFi) → POST /api/esp32/upload → main.py → Web
  serial_bridge.py chỉ MONITOR: GET từ backend để hiển thị

Cách dùng:
  python serial_bridge.py
"""
import requests
import time
import os
import json
import sys

# ════════════════ CONFIG ════════════════
API_URL = "http://localhost:8000"

# ════════════════ COLOR ════════════════
G = "\033[92m"   # Green
R = "\033[91m"   # Red
Y = "\033[93m"   # Yellow
C = "\033[96m"   # Cyan
B = "\033[1m"    # Bold
X = "\033[0m"    # Reset

# ════════════════ FUNCTIONS ════════════════
def check_backend():
    try:
        res = requests.get(f"{API_URL}/", timeout=3)
        return res.status_code == 200
    except Exception:
        return False

def get_esp32_info():
    try:
        res = requests.get(f"{API_URL}/api/esp32/info", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def get_sensor_data():
    try:
        res = requests.get(f"{API_URL}/api/sensor-data/latest", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def get_relay_status():
    try:
        res = requests.get(f"{API_URL}/api/relay/status", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def get_auto_status():
    try:
        res = requests.get(f"{API_URL}/api/auto/status", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

def relay_on_off(state):
    return f"{G}ON{X}" if state else f"{R}OFF{X}"

def display(esp_info, sensor, relay, auto_st, count):
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"{B}{'═' * 60}{X}")
    print(f"{B}  🌿 NHÀ KÍNH THÔNG MINH — WiFi Monitor (CHỈ ĐỌC){X}")
    print(f"{B}{'═' * 60}{X}")
    print()

    # ── ESP32 Connection ──
    if esp_info and esp_info.get("device_id"):
        last_seen = esp_info.get("last_seen", "")
        print(f"  {G}🟢 ESP32 ĐÃ KẾT NỐI WiFi{X}")
        print(f"     📡 Device : {esp_info.get('device_id', '?')}")
        print(f"     🌐 IP     : {esp_info.get('ip', '?')}")
        print(f"     📶 RSSI   : {esp_info.get('wifi_rssi', '?')} dBm")
        print(f"     🔄 Mode   : {esp_info.get('mode', '?')}")
        print(f"     ⏱️  Last   : {last_seen}")
    else:
        print(f"  {R}🔴 ESP32 CHƯA KẾT NỐI{X}")
        print(f"     → ESP32 phải kết nối WiFi và gửi data đến backend")
        print(f"     → Kiểm tra:")
        print(f"       1. ESP32 đã bật và nạp code C++ chưa?")
        print(f"       2. WiFi đúng tên + mật khẩu?")
        print(f"       3. IP backend trong code C++ đúng chưa?")
        print(f"          (const char* serverBase = \"http://IP_MÁY_BACKEND:8000\")")

    print(f"\n  {'─' * 56}")

    # ── Sensor Data (data THẬT từ ESP32) ──
    if sensor and sensor.get("air_temperature") is not None:
        print(f"  📊 {B}DỮ LIỆU CẢM BIẾN (từ ESP32 thật){X}")
        print(f"     🌡️  Nhiệt độ KK  : {sensor.get('air_temperature', '?')}°C")
        print(f"     💨 Độ ẩm KK     : {sensor.get('air_humidity', '?')}%")
        print(f"     🌡️  Nhiệt độ đất : {sensor.get('soil_temperature', '?')}°C")
        print(f"     🌱 Độ ẩm đất    : {sensor.get('soil_moisture', '?')}%")
        print(f"     ⚡ EC            : {sensor.get('ec', '?')} µS/cm")
        print(f"     🧪 pH            : {sensor.get('soil_ph', '?')}")
        print(f"     🧂 Độ mặn       : {sensor.get('salinity', '?')}")
        print(f"     🅽  Nitrogen      : {sensor.get('nitrogen', '?')} mg/kg")
        print(f"     🅿  Phosphorus    : {sensor.get('phosphorus', '?')} mg/kg")
        print(f"     🅺  Potassium     : {sensor.get('potassium', '?')} mg/kg")
    else:
        print(f"  📊 {Y}Chưa có dữ liệu — chờ ESP32 gửi qua WiFi...{X}")

    print(f"\n  {'─' * 56}")

    # ── Relay ──
    if relay:
        mode_str = "TỰ ĐỘNG" if (auto_st and auto_st.get("enabled")) else "THỦ CÔNG"
        print(f"  🎛️  {B}THIẾT BỊ{X}  ({mode_str})")
        print(f"     🔥 Sưởi      : {relay_on_off(relay.get('heater', False))}")
        print(f"     🌀 Quạt      : {relay_on_off(relay.get('fan', False))}")
        print(f"     💧 Bơm       : {relay_on_off(relay.get('pump', False))}")
        print(f"     🌫️  Phun sương : {relay_on_off(relay.get('mist', False))}")
        print(f"     💡 Đèn       : {relay_on_off(relay.get('light', False))}")

    print(f"\n  {'─' * 56}")

    # ── Thresholds ──
    if auto_st:
        th = auto_st.get("thresholds", {})
        print(f"  ⚙️  {B}NGƯỠNG TỰ ĐỘNG{X}")
        print(f"     🌡️  Nhiệt: {th.get('temp_low', '?')} - {th.get('temp_high', '?')}°C")
        print(f"     💨 Ẩm KK: {th.get('air_humi_low', '?')} - {th.get('air_humi_high', '?')}%")
        print(f"     🌱 Ẩm đất: {th.get('soil_humi_low', '?')} - {th.get('soil_humi_high', '?')}%")

    print()
    print(f"{B}{'═' * 60}{X}")
    print(f"  🔄 #{count}  |  Cập nhật mỗi 2s  |  Ctrl+C để thoát")
    print(f"  🌐 Backend: {API_URL}")
    print(f"  ★ Script này CHỈ ĐỌC — ESP32 gửi data qua WiFi trực tiếp")

def main():
    print(f"{B}🌿 NHÀ KÍNH THÔNG MINH — WiFi Monitor{X}")
    print(f"🌐 Backend: {API_URL}")
    print(f"★ CHỈ ĐỌC dữ liệu từ backend (KHÔNG gửi data giả)")
    print(f"★ ESP32 thật gửi data qua WiFi → main.py nhận → hiển thị ở đây")
    print()

    # Kiểm tra backend
    print("🔍 Kiểm tra backend...", end=" ")
    if check_backend():
        print(f"{G}OK!{X}")
    else:
        print(f"{R}KHÔNG CHẠY!{X}")
        print(f"\n❌ Backend chưa chạy!")
        print(f"   Mở terminal khác chạy: py main.py")
        return

    print("🔍 Chờ ESP32 kết nối qua WiFi...")
    print("   (Rút ESP32 → data sẽ dừng, không có data giả)\n")
    time.sleep(2)

    count = 0
    try:
        while True:
            count += 1
            esp_info = get_esp32_info()
            sensor = get_sensor_data()
            relay = get_relay_status()
            auto_st = get_auto_status()
            display(esp_info, sensor, relay, auto_st, count)
            time.sleep(2)

    except KeyboardInterrupt:
        print(f"\n\n🛑 Đã dừng monitor.")


if __name__ == "__main__":
    main()
