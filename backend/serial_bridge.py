"""
Serial Bridge v2: 
  1. Đọc data từ ESP32 qua Serial → gửi HTTP POST lên FastAPI backend
  2. Poll backend cho relay commands → gửi xuống ESP32 qua Serial

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
    """Thread: Poll backend cho relay commands → gửi xuống ESP32."""
    relay_name_map = {
        "heater": "HEATER",
        "fan": "FAN",
        "pump": "PUMP",
        "mist": "MIST",
        "light": "LIGHT",
    }

    while not stop_event.is_set():
        try:
            response = requests.get(f"{API_URL}/api/relay/pending", timeout=3)
            if response.status_code == 200:
                commands = response.json()
                for cmd in commands:
                    relay = cmd.get("relay", "")
                    state = cmd.get("state", False)
                    relay_upper = relay_name_map.get(relay, relay.upper())
                    serial_cmd = f"RELAY:{relay_upper}:{'ON' if state else 'OFF'}\n"
                    
                    ser.write(serial_cmd.encode())
                    print(f"   🎛️ Gửi lệnh: {serial_cmd.strip()}")
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"   ⚠️ Relay poll error: {e}")

        stop_event.wait(RELAY_POLL_INTERVAL)


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
    print(f"   Nhấn Ctrl+C để dừng\n")

    try:
        ser = serial.Serial(port, 115200, timeout=2)
        print(f"✅ Đã kết nối {port}!\n")
    except serial.SerialException as e:
        print(f"❌ Không mở được {port}: {e}")
        print("   Tắt Serial Monitor trong Arduino IDE trước khi chạy script này!")
        return

    # Start relay command poller thread
    stop_event = threading.Event()
    relay_thread = threading.Thread(target=relay_command_poller, args=(ser, stop_event), daemon=True)
    relay_thread.start()
    print("🎛️ Relay command thread started.\n")

    buffer = []
    count = 0

    try:
        while True:
            if ser.in_waiting:
                line = ser.readline().decode("utf-8", errors="ignore").strip()

                if not line:
                    continue

                print(f"   📡 {line}")

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
