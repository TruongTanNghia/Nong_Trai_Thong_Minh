"""
Test script mô phỏng ESP32 gửi data qua WiFi HTTP.
Gửi data lên POST /api/esp32/upload mỗi 3 giây (giống ESP32 thật).
Chạy: python test_send_data.py
"""
import requests
import time
import random
import json

API_URL = "http://localhost:8000"

def generate_mock_data():
    """Tạo data cảm biến giả lập."""
    return {
        "device_id": "esp32_gateway_01",
        "hasValidData": True,
        "mode": "AUTO",

        # Sensor data
        "airTemp": round(random.uniform(20.0, 35.0), 1),
        "airHumi": round(random.uniform(40.0, 90.0), 1),
        "soilTemp": round(random.uniform(18.0, 30.0), 1),
        "soilHumi": round(random.uniform(20.0, 80.0), 1),
        "salinity": random.randint(100, 500),
        "ec": random.randint(200, 1500),
        "nitrogen": random.randint(10, 100),
        "phosphorus": random.randint(5, 50),
        "potassium": random.randint(50, 200),
        "ph": round(random.uniform(5.0, 8.0), 1),

        # Relay states
        "heater": False,
        "fan": False,
        "pump": False,
        "mist": False,
        "light": False,

        # Settings
        "tempLow": 20.0,
        "tempHigh": 30.0,
        "airHumiLow": 60.0,
        "airHumiHigh": 80.0,
        "soilHumiLow": 30.0,
        "soilHumiHigh": 60.0,

        # WiFi info
        "wifi_rssi": random.randint(-80, -30),
        "ip": "192.168.0.101",
    }


def main():
    print("🧪 Test ESP32 WiFi Direct Mode")
    print(f"📡 Server: {API_URL}")
    print(f"📤 Upload endpoint: /api/esp32/upload")
    print(f"📥 Command endpoint: /api/esp32/command")
    print(f"⏱️  Upload mỗi 3 giây (giống ESP32 thật)")
    print(f"   Nhấn Ctrl+C để dừng\n")

    count = 0

    try:
        while True:
            count += 1
            data = generate_mock_data()

            # ── Upload data (giống ESP32 uploadDataToServer) ──
            try:
                res = requests.post(f"{API_URL}/api/esp32/upload", json=data, timeout=5)
                if res.status_code == 200:
                    print(f"📤 [{count}] Upload OK — "
                          f"T:{data['airTemp']}°C  H:{data['airHumi']}%  "
                          f"Soil:{data['soilHumi']}%  pH:{data['ph']}")
                else:
                    print(f"❌ [{count}] Upload failed: HTTP {res.status_code}")
            except requests.exceptions.ConnectionError:
                print(f"⚠️ [{count}] Không kết nối backend! Kiểm tra: python main.py")
            except Exception as e:
                print(f"❌ [{count}] Lỗi upload: {e}")

            # ── Fetch commands (giống ESP32 fetchCommandFromServer) ──
            try:
                res = requests.get(
                    f"{API_URL}/api/esp32/command",
                    params={"device_id": "esp32_gateway_01"},
                    timeout=3
                )
                if res.status_code == 200:
                    cmd = res.json()
                    if cmd:
                        print(f"📥 [{count}] Command nhận được: {json.dumps(cmd, ensure_ascii=False)}")
            except Exception:
                pass

            time.sleep(3)

    except KeyboardInterrupt:
        print(f"\n🛑 Dừng. Đã gửi {count} lần.")


if __name__ == "__main__":
    main()
