"""
Test script: Gửi mock sensor data đến FastAPI backend
Dùng để test dashboard mà không cần ESP32 thật

Chạy: python test_send_data.py
"""
import requests
import time
import random
import math

API_URL = "http://localhost:8000/api/sensor-data"

def generate_mock_data():
    """Generate realistic mock sensor data with slight variations."""
    t = time.time()
    return {
        "soil_temperature": round(22 + 3 * math.sin(t / 60) + random.uniform(-0.5, 0.5), 1),
        "soil_moisture": round(45 + 10 * math.sin(t / 120) + random.uniform(-2, 2), 1),
        "soil_ph": round(6.5 + 0.5 * math.sin(t / 180) + random.uniform(-0.1, 0.1), 1),
        "ec": round(350 + 100 * math.sin(t / 90) + random.uniform(-20, 20)),
        "nitrogen": round(36 + 10 * math.sin(t / 150) + random.uniform(-3, 3)),
        "phosphorus": round(25 + 8 * math.sin(t / 200) + random.uniform(-2, 2)),
        "potassium": round(120 + 30 * math.sin(t / 100) + random.uniform(-5, 5)),
        "salinity": round(80 + 20 * math.sin(t / 160) + random.uniform(-5, 5)),
        "air_temperature": round(28 + 4 * math.sin(t / 80) + random.uniform(-0.3, 0.3), 1),
        "air_humidity": round(65 + 10 * math.sin(t / 100) + random.uniform(-2, 2), 1),
        "light_intensity": round(max(0, 30000 + 20000 * math.sin(t / 200) + random.uniform(-1000, 1000))),
    }

def main():
    print("🚀 Bắt đầu gửi mock sensor data đến:", API_URL)
    print("   Nhấn Ctrl+C để dừng\n")

    count = 0
    while True:
        try:
            data = generate_mock_data()
            response = requests.post(API_URL, json=data, timeout=5)

            count += 1
            if response.status_code == 200:
                print(f"✅ [{count}] Sent: T_soil={data['soil_temperature']}°C "
                      f"M={data['soil_moisture']}% pH={data['soil_ph']} "
                      f"EC={data['ec']} N={data['nitrogen']} P={data['phosphorus']} "
                      f"K={data['potassium']} T_air={data['air_temperature']}°C "
                      f"H={data['air_humidity']}% Light={data['light_intensity']}lux")
            else:
                print(f"❌ [{count}] HTTP {response.status_code}: {response.text}")

            time.sleep(3)  # Gửi mỗi 3 giây

        except requests.exceptions.ConnectionError:
            print("⚠️ Không kết nối được server. Đảm bảo backend đang chạy!")
            print("   Chạy: cd backend && python main.py")
            time.sleep(5)
        except KeyboardInterrupt:
            print(f"\n🛑 Dừng. Đã gửi {count} lần.")
            break

if __name__ == "__main__":
    main()
