"""Test auto-control with extreme values."""
import requests
import time

API = "http://localhost:8000"

# 1. Bật auto mode
r = requests.post(f"{API}/api/auto/toggle")
auto_status = r.json()
print(f"Auto mode: {auto_status}")

# Nếu đang OFF, toggle lần nữa
if not auto_status.get("enabled"):
    r = requests.post(f"{API}/api/auto/toggle")
    print(f"Toggle again: {r.json()}")

time.sleep(1)

# 2. Gửi data NGOÀI NGƯỠNG
extreme_data = {
    "air_temperature": 15.0,    # < 20 → bật Sưởi
    "air_humidity": 45.0,       # < 60 → bật Phun sương
    "soil_temperature": 18.0,
    "soil_moisture": 20.0,      # < 30 → bật Bơm
    "soil_ph": 6.5,
    "ec": 400,
    "nitrogen": 30,
    "phosphorus": 20,
    "potassium": 100,
    "salinity": 150,
    "light_intensity": 2000,    # < 5000 → bật Đèn
}
print(f"\nGửi data extreme: temp={extreme_data['air_temperature']}°C, humi={extreme_data['air_humidity']}%, soil={extreme_data['soil_moisture']}%, light={extreme_data['light_intensity']}lux")
r = requests.post(f"{API}/api/sensor-data", json=extreme_data)
print(f"Response: {r.json()}")

time.sleep(2)

# 3. Kiểm tra relay
print(f"\nRelay states: {requests.get(f'{API}/api/relay/status').json()}")
auto_info = requests.get(f"{API}/api/auto/status").json()
print(f"Auto enabled: {auto_info['enabled']}")
print(f"Log entries: {len(auto_info['log'])}")
for entry in auto_info['log'][-10:]:
    print(f"  [{entry['time']}] {entry['relay']} → {'ON' if entry['state'] else 'OFF'} | {entry['reason']}")
