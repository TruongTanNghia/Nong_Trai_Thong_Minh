"""
Serial Bridge v4: ESP32 ↔ Web bidirectional sync
  1. Đọc data từ ESP32 qua Serial → gửi HTTP POST lên FastAPI backend
  2. Poll backend cho relay commands → gửi xuống ESP32 qua Serial
  3. Đọc CFG từ ESP32 → POST lên /api/auto/thresholds (ESP32 → Web)
  4. Poll settings commands → gửi CFG xuống ESP32 (Web → ESP32)
  5. ★ Đọc MODE từ ESP32 → POST lên /api/mode/sync-from-device
  6. ★ Poll mode commands → gửi MODE xuống ESP32 (Web → ESP32)
  7. ★ Startup sync: GET:MODE, GET:CFG, GET:RELAY

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
RELAY_POLL_INTERVAL = 1.0  # Poll mỗi 1 giây


def find_esp32_port():
    """Tự tìm COM port của ESP32."""
    ports = serial.tools.list_ports.comports()
    print(f"📋 Tìm thấy {len(ports)} cổng COM:")
    for p in ports:
        print(f"   {p.device} - {p.description}")
        if any(keyword in p.description.upper() for keyword in ["CP210", "CH340", "USB-SERIAL", "ESP32", "SILICON"]):
            print(f"   ✓ Có thể là ESP32!")
            return p.device

    if ports:
        print(f"\n⚠️ Không tìm thấy ESP32, thử dùng port đầu tiên: {ports[0].device}")
        return ports[0].device

    return None


def parse_serial_data(lines):
    """Parse data từ Serial output của ESP32."""
    data = {}
    mapping = {
        "Air Temp": "air_temperature",
        "Air Humi": "air_humidity",
        "Soil Temp": "soil_temperature",
        "Soil Humi": "soil_moisture",
        "Salinity": "salinity",
        "EC": "ec",
        "N": "nitrogen",
        "P": "phosphorus",
        "K": "potassium",
        "pH": "soil_ph",
    }
    
    for line in lines:
        for serial_key, api_key in mapping.items():
            if line.startswith(serial_key + ":"):
                try:
                    value_str = line.split(":")[1].strip()
                    value = float(value_str)
                    data[api_key] = value
                except (ValueError, IndexError):
                    pass

    return data if len(data) >= 5 else None


# ★ Parse CFG line from ESP32 → POST to backend
def parse_cfg_line(line):
    """Parse CFG:tempLow=20.0,tempHigh=30.0,... from ESP32."""
    cfg_str = line[4:]  # skip "CFG:"
    thresholds = {}
    
    # Map ESP32 key names → backend API key names
    key_map = {
        "tempLow": "temp_low",
        "tempHigh": "temp_high",
        "airHumiLow": "air_humi_low",
        "airHumiHigh": "air_humi_high",
        "soilHumiLow": "soil_humi_low",
        "soilHumiHigh": "soil_humi_high",
    }
    
    for pair in cfg_str.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            key = key.strip()
            api_key = key_map.get(key)
            if api_key:
                try:
                    thresholds[api_key] = float(val.strip())
                except ValueError:
                    pass

    return thresholds if thresholds else None


# ★ Parse RELAY_STATE line from ESP32 → POST to backend
def parse_relay_state_line(line):
    """Parse RELAY_STATE:heater=1,fan=0,pump=0,mist=0,light=0 from ESP32."""
    state_str = line[len("RELAY_STATE:"):]
    states = {}

    for pair in state_str.split(","):
        if "=" in pair:
            key, val = pair.split("=", 1)
            key = key.strip()
            try:
                states[key] = int(val.strip()) == 1
            except ValueError:
                pass

    return states if states else None


# ★ Parse MODE line from ESP32 → POST to backend
def parse_mode_line(line):
    """Parse MODE:AUTO or MODE:MANUAL from ESP32."""
    mode_str = line[5:]  # skip "MODE:"
    mode_str = mode_str.strip().upper()
    if mode_str in ("AUTO", "MANUAL"):
        return mode_str
    return None


def send_relay_state_to_server(states):
    """POST trạng thái relay từ ESP32 lên backend."""
    try:
        response = requests.post(f"{API_URL}/api/relay/sync-from-device", json=states, timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Đồng bộ relay ESP32 → Web: {states}")
        else:
            print(f"   ❌ Lỗi sync relay: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Không kết nối được backend!")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")


def send_cfg_to_server(thresholds):
    """POST ngưỡng từ ESP32 lên backend."""
    try:
        response = requests.post(f"{API_URL}/api/auto/thresholds", json=thresholds, timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Đồng bộ ngưỡng ESP32 → Web thành công!")
            print(f"      {thresholds}")
        else:
            print(f"   ❌ Lỗi sync ngưỡng: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Không kết nối được backend!")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")


# ★ Gửi mode từ ESP32 lên backend
def send_mode_to_server(mode):
    """POST mode (AUTO/MANUAL) từ ESP32 lên backend."""
    try:
        response = requests.post(
            f"{API_URL}/api/mode/sync-from-device",
            json={"mode": mode},
            timeout=5
        )
        if response.status_code == 200:
            print(f"   ✅ Đồng bộ mode ESP32 → Web: {mode}")
        else:
            print(f"   ❌ Lỗi sync mode: HTTP {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Không kết nối được backend!")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")


def send_to_server(data):
    """Gửi sensor data lên FastAPI backend."""
    try:
        response = requests.post(f"{API_URL}/api/sensor-data", json=data, timeout=5)
        if response.status_code == 200:
            print(f"   ✅ Gửi thành công! ({len(data)} tham số)")
        else:
            print(f"   ❌ Lỗi HTTP: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Không kết nối được backend! Kiểm tra: python main.py đang chạy?")
    except Exception as e:
        print(f"   ❌ Lỗi: {e}")


def relay_command_poller(ser, stop_event):
    """Thread: Poll backend cho relay commands + settings commands + mode commands → gửi xuống ESP32."""
    relay_name_map = {
        "heater": "HEATER",
        "fan": "FAN",
        "pump": "PUMP",
        "mist": "MIST",
        "light": "LIGHT",
    }
    
    # ★ Map backend key → ESP32 key
    threshold_key_map = {
        "temp_low": "tempLow",
        "temp_high": "tempHigh",
        "air_humi_low": "airHumiLow",
        "air_humi_high": "airHumiHigh",
        "soil_humi_low": "soilHumiLow",
        "soil_humi_high": "soilHumiHigh",
    }

    while not stop_event.is_set():
        try:
            # Poll relay commands
            response = requests.get(f"{API_URL}/api/relay/pending", timeout=3)
            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    cmd_type = cmd.get("type", "relay_command")
                    
                    if cmd_type == "relay_command":
                        relay = cmd.get("relay", "")
                        state = cmd.get("state", False)
                        relay_upper = relay_name_map.get(relay, relay.upper())
                        serial_cmd = f"RELAY:{relay_upper}:{'ON' if state else 'OFF'}\n"
                        ser.write(serial_cmd.encode())
                        print(f"   🎛️ Gửi lệnh: {serial_cmd.strip()}")
                    
                    elif cmd_type == "settings_command":
                        # ★ Web → ESP32: gửi ngưỡng mới
                        thresholds = cmd.get("thresholds", {})
                        parts = []
                        for api_key, esp_key in threshold_key_map.items():
                            if api_key in thresholds:
                                parts.append(f"{esp_key}={thresholds[api_key]}")
                        if parts:
                            cfg_cmd = "CFG:" + ",".join(parts) + "\n"
                            ser.write(cfg_cmd.encode())
                            print(f"   ⚙️ Gửi ngưỡng → ESP32: {cfg_cmd.strip()}")
                    
                    elif cmd_type == "mode_command":
                        # ★ Web → ESP32: gửi lệnh chuyển mode
                        mode = cmd.get("mode", "")
                        if mode in ("AUTO", "MANUAL"):
                            mode_cmd = f"MODE:{mode}\n"
                            ser.write(mode_cmd.encode())
                            print(f"   🔄 Gửi mode → ESP32: {mode_cmd.strip()}")

        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"   ⚠️ Relay poll error: {e}")

        stop_event.wait(RELAY_POLL_INTERVAL)


# ★ Startup sync: query current state from ESP32
def startup_sync(ser):
    """Gửi GET commands để đồng bộ trạng thái ban đầu từ ESP32."""
    print("🔄 Startup sync: querying ESP32 state...")
    time.sleep(1)  # Chờ ESP32 sẵn sàng
    
    queries = ["GET:MODE\n", "GET:CFG\n", "GET:RELAY\n"]
    for q in queries:
        try:
            ser.write(q.encode())
            print(f"   📤 Sent: {q.strip()}")
            time.sleep(0.3)  # Chờ ESP32 phản hồi
        except Exception as e:
            print(f"   ⚠️ Lỗi gửi {q.strip()}: {e}")


def main():
    # Tìm COM port
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        port = find_esp32_port()

    if not port:
        print("❌ Không tìm thấy COM port! Cắm ESP32 vào và thử lại.")
        print("   Hoặc chỉ định: python serial_bridge.py COM5")
        return

    print(f"\n🔌 Kết nối Serial: {port} @ 115200 baud")
    print(f"🌐 Backend: {API_URL}")
    print(f"🎛️ Relay command polling: mỗi {RELAY_POLL_INTERVAL}s")
    print(f"⚙️ Threshold sync: ESP32 ↔ Web bidirectional")
    print(f"🔄 Mode sync: ESP32 ↔ Web bidirectional")
    print(f"   Nhấn Ctrl+C để dừng\n")

    try:
        ser = serial.Serial(port, 115200, timeout=2)
        print(f"✅ Đã kết nối {port}!\n")
    except serial.SerialException as e:
        print(f"❌ Không mở được {port}: {e}")
        print("   Tắt Serial Monitor trong Arduino IDE trước khi chạy script này!")
        return

    # ★ Startup sync: query ESP32 state
    startup_sync(ser)

    # Start relay command poller thread
    stop_event = threading.Event()
    relay_thread = threading.Thread(target=relay_command_poller, args=(ser, stop_event), daemon=True)
    relay_thread.start()
    print("🎛️ Relay + Settings + Mode command thread started.\n")

    buffer = []
    count = 0

    try:
        while True:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()

                if not line:
                    continue

                print(f"   📡 {line}")

                # ★ Handle CFG line from ESP32
                if line.startswith("CFG:"):
                    thresholds = parse_cfg_line(line)
                    if thresholds:
                        print(f"\n⚙️ ESP32 gửi ngưỡng mới:")
                        send_cfg_to_server(thresholds)
                        print()
                    continue

                # ★ Handle RELAY_STATE from ESP32
                if line.startswith("RELAY_STATE:"):
                    states = parse_relay_state_line(line)
                    if states:
                        print(f"\n🏛️ ESP32 relay thay đổi:")
                        send_relay_state_to_server(states)
                        print()
                    continue

                # ★ Handle MODE from ESP32
                if line.startswith("MODE:"):
                    mode = parse_mode_line(line)
                    if mode:
                        print(f"\n🔄 ESP32 mode thay đổi:")
                        send_mode_to_server(mode)
                        print()
                    continue

                # ★ Bỏ qua info messages từ ESP32
                if line.startswith(">>"):
                    continue

                if "DATA NODE" in line:
                    buffer = []
                elif "=====" in line and buffer:
                    data = parse_serial_data(buffer)
                    if data:
                        count += 1
                        print(f"\n📤 [{count}] Gửi data lên server...")
                        send_to_server(data)
                        print()
                    buffer = []
                elif buffer is not None:
                    buffer.append(line)

    except KeyboardInterrupt:
        print(f"\n🛑 Dừng. Đã gửi {count} lần.")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
    finally:
        stop_event.set()
        relay_thread.join(timeout=2)
        ser.close()
        print("🔌 Đã đóng Serial.")


if __name__ == "__main__":
    main()
