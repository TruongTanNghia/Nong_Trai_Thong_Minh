"""
Serial Bridge v5 — Dành cho firmware WiFi HTTP mới
Đọc debug output từ ESP32 qua USB Serial → gửi lên backend.
Dùng làm BACKUP khi WiFi ESP32 không ổn định,
hoặc để MONITOR data trên máy tính nối USB.

Firmware mới ESP32 gửi data qua WiFi HTTP trực tiếp (là kênh chính).
Serial bridge đọc Serial debug output làm kênh phụ/backup.

Cách dùng:
  python serial_bridge.py          (tự tìm COM port)
  python serial_bridge.py COM5     (chỉ định COM port)
"""
import serial
import serial.tools.list_ports
import requests
import sys
import time
import threading

API_URL = "http://localhost:8000"
COMMAND_POLL_INTERVAL = 1.0


def find_esp32_port():
    """Tự tìm COM port của ESP32."""
    ports = serial.tools.list_ports.comports()
    print(f"📋 Tìm thấy {len(ports)} cổng COM:")
    for p in ports:
        print(f"   {p.device} - {p.description}")
        if any(kw in p.description.upper() for kw in
               ["CP210", "CH340", "USB-SERIAL", "ESP32", "SILICON"]):
            print(f"   ✓ Có thể là ESP32!")
            return p.device

    if ports:
        print(f"\n⚠️ Không tìm thấy ESP32, dùng port đầu: {ports[0].device}")
        return ports[0].device
    return None


# ═══════════════════════════════════════════════════
# Parse Serial output từ ESP32
# ═══════════════════════════════════════════════════

# Lưu state hiện tại (ghép từ nhiều dòng serial)
current_sensor = {}
current_relay = {}
current_cfg = {}
current_mode = "AUTO"


def parse_sensor_line(line):
    """Parse 1 dòng sensor trong block DATA NODE."""
    mapping = {
        "Air Temp": "airTemp",
        "Air Humi": "airHumi",
        "Soil Temp": "soilTemp",
        "Soil Humi": "soilHumi",
        "Salinity": "salinity",
        "EC": "ec",
        "N": "nitrogen",
        "P": "phosphorus",
        "K": "potassium",
        "pH": "ph",
    }
    for serial_key, json_key in mapping.items():
        if line.startswith(serial_key + ":"):
            try:
                val = line.split(":", 1)[1].strip()
                current_sensor[json_key] = float(val)
                return True
            except (ValueError, IndexError):
                pass
    return False


def parse_relay_state_line(line):
    """Parse RELAY_STATE:heater=1,fan=0,..."""
    global current_relay
    state_str = line[len("RELAY_STATE:"):]
    for pair in state_str.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            try:
                current_relay[key.strip()] = int(val.strip()) == 1
            except ValueError:
                pass


def parse_cfg_line(line):
    """Parse CFG:tempLow=20.0,tempHigh=30.0,..."""
    global current_cfg
    cfg_str = line[4:]
    for pair in cfg_str.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            try:
                current_cfg[key.strip()] = float(val.strip())
            except ValueError:
                pass


def build_upload_payload():
    """Ghép toàn bộ state thành payload giống ESP32 uploadDataToServer()."""
    payload = {
        "device_id": "esp32_gateway_01",
        "hasValidData": len(current_sensor) >= 5,
        "mode": current_mode,

        # Sensor data
        "airTemp": current_sensor.get("airTemp", 0),
        "airHumi": current_sensor.get("airHumi", 0),
        "soilTemp": current_sensor.get("soilTemp", 0),
        "soilHumi": current_sensor.get("soilHumi", 0),
        "salinity": current_sensor.get("salinity", 0),
        "ec": current_sensor.get("ec", 0),
        "nitrogen": current_sensor.get("nitrogen", 0),
        "phosphorus": current_sensor.get("phosphorus", 0),
        "potassium": current_sensor.get("potassium", 0),
        "ph": current_sensor.get("ph", 0),

        # Relay states
        "heater": current_relay.get("heater", False),
        "fan": current_relay.get("fan", False),
        "pump": current_relay.get("pump", False),
        "mist": current_relay.get("mist", False),
        "light": current_relay.get("light", False),

        # Settings
        "tempLow": current_cfg.get("tempLow", 20.0),
        "tempHigh": current_cfg.get("tempHigh", 30.0),
        "airHumiLow": current_cfg.get("airHumiLow", 60.0),
        "airHumiHigh": current_cfg.get("airHumiHigh", 80.0),
        "soilHumiLow": current_cfg.get("soilHumiLow", 30.0),
        "soilHumiHigh": current_cfg.get("soilHumiHigh", 60.0),

        # WiFi info (qua serial không có, ghi USB)
        "wifi_rssi": 0,
        "ip": "USB-Serial",
    }
    return payload


def upload_to_server(payload):
    """POST lên /api/esp32/upload — cùng endpoint ESP32 WiFi dùng."""
    try:
        res = requests.post(f"{API_URL}/api/esp32/upload", json=payload, timeout=5)
        if res.status_code == 200:
            print(f"   ✅ Gửi lên backend OK!")
        else:
            print(f"   ❌ HTTP {res.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Backend không chạy! Kiểm tra: python main.py")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")


# ═══════════════════════════════════════════════════
# Command poller: lấy lệnh từ web → gửi xuống ESP32
# Firmware mới KHÔNG đọc serial commands,
# nhưng ESP32 tự poll qua WiFi HTTP.
# Thread này chỉ LOG để monitor.
# ═══════════════════════════════════════════════════

def command_monitor(stop_event):
    """Monitor pending commands (chỉ hiển thị, ESP32 tự lấy qua WiFi)."""
    while not stop_event.is_set():
        try:
            res = requests.get(f"{API_URL}/api/esp32/command",
                               params={"device_id": "esp32_gateway_01"},
                               timeout=3)
            if res.status_code == 200:
                cmd = res.json()
                if cmd:
                    print(f"   📥 Lệnh từ web (ESP32 sẽ nhận qua WiFi): {cmd}")
        except Exception:
            pass
        stop_event.wait(COMMAND_POLL_INTERVAL)


# ═══════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════

def main():
    global current_mode

    port = sys.argv[1] if len(sys.argv) > 1 else find_esp32_port()

    if not port:
        print("❌ Không tìm thấy COM port!")
        print("   Cắm ESP32 vào USB và thử lại.")
        print("   Hoặc chỉ định: python serial_bridge.py COM5")
        return

    print(f"\n🔌 Kết nối Serial: {port} @ 115200 baud")
    print(f"🌐 Backend: {API_URL}")
    print(f"📡 Đọc data từ ESP32 Serial → gửi lên /api/esp32/upload")
    print(f"   Nhấn Ctrl+C để dừng\n")

    try:
        ser = serial.Serial(port, 115200, timeout=2)
        print(f"✅ Đã kết nối {port}!\n")
    except serial.SerialException as e:
        print(f"❌ Không mở được {port}: {e}")
        print("   Tắt Serial Monitor trong Arduino IDE!")
        return

    stop_event = threading.Event()

    in_data_block = False
    count = 0

    try:
        while True:
            if not ser.in_waiting:
                time.sleep(0.01)
                continue

            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            print(f"   📡 {line}")

            # ── Detect WiFi status ──
            if "WIFI CONNECTED" in line:
                print("\n   🟢 ESP32 WiFi đã kết nối!")
            elif "WIFI CONNECT FAILED" in line:
                print("\n   🔴 ESP32 WiFi thất bại — Serial bridge sẽ gửi data thay!")

            # ── Parse [UPLOAD] logs từ ESP32 ──
            if line.startswith("[UPLOAD] HTTP code:"):
                code = line.split(":")[1].strip()
                if code == "200":
                    print("   ✅ ESP32 WiFi upload OK")
                else:
                    print(f"   ⚠️ ESP32 WiFi upload lỗi: HTTP {code}")
                continue

            # ── Parse RELAY_STATE ──
            if line.startswith("RELAY_STATE:"):
                parse_relay_state_line(line)
                print(f"   🎛️ Relay: {current_relay}")
                continue

            # ── Parse CFG ──
            if line.startswith("CFG:"):
                parse_cfg_line(line)
                print(f"   ⚙️ Settings: {current_cfg}")
                continue

            # ── Parse DATA NODE block ──
            if "===== DATA NODE =====" in line:
                in_data_block = True
                current_sensor.clear()
                continue

            if in_data_block:
                if "=====================" in line:
                    # Kết thúc block → gửi lên backend
                    in_data_block = False
                    count += 1

                    payload = build_upload_payload()
                    print(f"\n📤 [{count}] Gửi data lên backend...")
                    print(f"   T:{current_sensor.get('airTemp')}°C  "
                          f"H:{current_sensor.get('airHumi')}%  "
                          f"Soil:{current_sensor.get('soilHumi')}%  "
                          f"pH:{current_sensor.get('ph')}")
                    upload_to_server(payload)
                    print()
                else:
                    parse_sensor_line(line)
                continue

            # ── Bỏ qua debug messages ──
            if line.startswith(">>") or line.startswith("[CMD]"):
                continue

    except KeyboardInterrupt:
        print(f"\n🛑 Dừng. Đã gửi {count} lần.")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
    finally:
        stop_event.set()
        ser.close()
        print("🔌 Đã đóng Serial.")


if __name__ == "__main__":
    main()
