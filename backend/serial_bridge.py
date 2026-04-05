"""
WiFi Bridge v6 — Monitor ESP32 qua WiFi (KHÔNG CẦN USB)
ESP32 gửi data qua WiFi → main.py nhận → script này hiển thị.

Chỉ cần:
  1. py main.py          (backend nhận data từ ESP32 WiFi)
  2. py serial_bridge.py (monitor hiển thị data + trạng thái)

KHÔNG CẦN cắm USB!
"""
import requests
import time
import json
import sys
import os

API_URL = "http://localhost:8000"
POLL_INTERVAL = 2  # Poll mỗi 2 giây

# Màu console
class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def clear_line():
    print("\r" + " " * 80 + "\r", end="")


def check_backend():
    """Kiểm tra backend có chạy không."""
    try:
        res = requests.get(f"{API_URL}/", timeout=3)
        return res.status_code == 200
    except Exception:
        return False


def get_esp32_info():
    """Lấy thông tin ESP32 device."""
    try:
        res = requests.get(f"{API_URL}/api/esp32/info", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def get_sensor_data():
    """Lấy data cảm biến mới nhất."""
    try:
        res = requests.get(f"{API_URL}/api/sensor-data/latest", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def get_relay_status():
    """Lấy trạng thái relay."""
    try:
        res = requests.get(f"{API_URL}/api/relay/status", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def get_auto_status():
    """Lấy trạng thái auto mode."""
    try:
        res = requests.get(f"{API_URL}/api/auto/status", timeout=3)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def format_relay(name, state):
    """Format relay state với màu."""
    if state:
        return f"{Color.GREEN}ON{Color.RESET}"
    return f"{Color.RED}OFF{Color.RESET}"


def display_status(esp_info, sensor, relay, auto_status, count):
    """Hiển thị toàn bộ trạng thái."""
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"{Color.BOLD}{'═' * 60}{Color.RESET}")
    print(f"{Color.BOLD}  🌿 NHÀ KÍNH THÔNG MINH — WiFi Monitor{Color.RESET}")
    print(f"{Color.BOLD}{'═' * 60}{Color.RESET}")
    print()

    # ── ESP32 Info ──
    if esp_info and esp_info.get("device_id"):
        print(f"  {Color.GREEN}🟢 ESP32 ĐÃ KẾT NỐI WiFi{Color.RESET}")
        print(f"     📡 Device : {esp_info.get('device_id', '?')}")
        print(f"     🌐 IP     : {esp_info.get('ip', '?')}")
        print(f"     📶 RSSI   : {esp_info.get('wifi_rssi', '?')} dBm")
        print(f"     🔄 Mode   : {esp_info.get('mode', '?')}")
        print(f"     ⏱️  Last   : {esp_info.get('last_seen', '?')}")
    else:
        print(f"  {Color.RED}🔴 ESP32 CHƯA KẾT NỐI{Color.RESET}")
        print(f"     Kiểm tra:")
        print(f"     1. ESP32 đã bật chưa?")
        print(f"     2. WiFi đúng tên + mật khẩu?")
        print(f"     3. IP backend đúng chưa? (trong code C++)")

    print()
    print(f"  {'─' * 56}")

    # ── Sensor Data ──
    if sensor and sensor.get("air_temperature") is not None:
        print(f"  📊 {Color.BOLD}DỮ LIỆU CẢM BIẾN{Color.RESET}")
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
        print(f"  📊 {Color.YELLOW}Chưa có dữ liệu cảm biến{Color.RESET}")

    print()
    print(f"  {'─' * 56}")

    # ── Relay States ──
    if relay:
        mode_str = "TỰ ĐỘNG" if (auto_status and auto_status.get("enabled")) else "THỦ CÔNG"
        print(f"  🎛️  {Color.BOLD}THIẾT BỊ{Color.RESET}  ({mode_str})")
        print(f"     🔥 Sưởi      : {format_relay('Sưởi', relay.get('heater', False))}")
        print(f"     🌀 Quạt      : {format_relay('Quạt', relay.get('fan', False))}")
        print(f"     💧 Bơm       : {format_relay('Bơm', relay.get('pump', False))}")
        print(f"     🌫️  Phun sương : {format_relay('Phun sương', relay.get('mist', False))}")
        print(f"     💡 Đèn       : {format_relay('Đèn', relay.get('light', False))}")

    print()
    print(f"  {'─' * 56}")

    # ── Thresholds ──
    if auto_status:
        th = auto_status.get("thresholds", {})
        print(f"  ⚙️  {Color.BOLD}NGƯỠNG TỰ ĐỘNG{Color.RESET}")
        print(f"     🌡️  Nhiệt độ : {th.get('temp_low', '?')} - {th.get('temp_high', '?')}°C")
        print(f"     💨 Độ ẩm KK : {th.get('air_humi_low', '?')} - {th.get('air_humi_high', '?')}%")
        print(f"     🌱 Độ ẩm đất: {th.get('soil_humi_low', '?')} - {th.get('soil_humi_high', '?')}%")

    print()
    print(f"{Color.BOLD}{'═' * 60}{Color.RESET}")
    print(f"  🔄 Cập nhật #{count}  |  Poll mỗi {POLL_INTERVAL}s  |  Ctrl+C để thoát")
    print(f"  🌐 Backend: {API_URL}  |  Web: http://localhost:3000")


def main():
    print(f"🌿 NHÀ KÍNH THÔNG MINH — WiFi Monitor")
    print(f"🌐 Backend: {API_URL}")
    print(f"📡 Kết nối qua WiFi — KHÔNG CẦN USB!")
    print(f"⏱️  Poll mỗi {POLL_INTERVAL} giây")
    print(f"   Nhấn Ctrl+C để dừng\n")

    # Kiểm tra backend
    print("🔍 Kiểm tra backend...", end=" ")
    if check_backend():
        print(f"{Color.GREEN}OK!{Color.RESET}")
    else:
        print(f"{Color.RED}KHÔNG CHẠY!{Color.RESET}")
        print(f"\n❌ Backend chưa chạy!")
        print(f"   Mở terminal khác chạy: py main.py")
        return

    print("🔍 Chờ ESP32 kết nối qua WiFi...\n")

    count = 0
    try:
        while True:
            count += 1

            esp_info = get_esp32_info()
            sensor = get_sensor_data()
            relay = get_relay_status()
            auto_status = get_auto_status()

            display_status(esp_info, sensor, relay, auto_status, count)

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n🛑 Đã dừng monitor.")


if __name__ == "__main__":
    main()
