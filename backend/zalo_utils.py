import requests
import datetime
import json
import os

# Đường dẫn file config lưu token và chat_id
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "zalo_config.json")

def load_zalo_config():
    """Load config từ file JSON. Nếu không có trả về dict rỗng."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Lỗi đọc file config Zalo: {e}")
    return {"bot_token": "", "chat_id": ""}

def save_zalo_config(token: str, chat_id: str, send_interval: int = 30):
    """Lưu config vào file JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"bot_token": token, "chat_id": chat_id, "send_interval": send_interval}, f, indent=4)
        return True
    except Exception as e:
        print(f"⚠️ Lỗi lưu file config Zalo: {e}")
        return False

def _extract_chat_id(data):
    """Trích xuất chat_id từ response của Zalo ZApps Bot API."""
    
    # Lấy result (có thể là dict hoặc list)
    result = data.get("result") if isinstance(data, dict) else data
    
    # Trường hợp 1: result là dict đơn lẻ (Zalo format)
    # {"result": {"message": {"chat": {"id": "xxx"}, "from": {"id": "xxx"}}}}
    if isinstance(result, dict):
        msg = result.get("message", result)
        if isinstance(msg, dict):
            # Thử lấy từ chat.id
            chat = msg.get("chat", {})
            if isinstance(chat, dict) and chat.get("id"):
                return str(chat["id"])
            # Thử lấy từ from.id
            sender = msg.get("from", {})
            if isinstance(sender, dict) and sender.get("id"):
                return str(sender["id"])
    
    # Trường hợp 2: result là list (Telegram-like format)
    if isinstance(result, list) and len(result) > 0:
        return _extract_chat_id({"result": result[-1]})
    
    return None


def fetch_chat_id_from_updates(bot_token: str):
    """
    Gọi API getUpdates của Zalo để lấy chat_id (người dùng phải gửi tin nhắn cho bot trước).
    Trả về (chat_id, error_message). Nếu thành công error_message là None.
    """
    if not bot_token:
        return None, "Vui lòng nhập Bot Token."

    url = f"https://bot-api.zapps.me/bot{bot_token}/getUpdates"
    try:
        res = requests.get(url, timeout=10)
        raw_text = res.text
        print(f"📡 Zalo getUpdates raw response (HTTP {res.status_code}):")
        print(f"   {raw_text[:500]}")
        
        data = res.json()
        
        # Kiểm tra lỗi xác thực
        if res.status_code == 401 or data.get("error_code") == 401:
            return None, "Bot Token không hợp lệ. Vui lòng kiểm tra lại."
        
        if res.status_code != 200:
            desc = data.get("description", raw_text[:200])
            return None, f"Lỗi từ Zalo API (HTTP {res.status_code}): {desc}"
        
        # Thử trích xuất chat_id
        chat_id = _extract_chat_id(data)
        
        if chat_id:
            print(f"   ✅ Tìm thấy Chat ID: {chat_id}")
            return chat_id, None
        
        # Không tìm được → trả lỗi chi tiết kèm raw response
        return None, f"Không trích xuất được Chat ID từ response. Vui lòng gửi tin nhắn cho Bot trên Zalo rồi thử lại. (Raw: {raw_text[:200]})"
            
    except requests.exceptions.Timeout:
        return None, "Kết nối đến Zalo API bị quá giờ (timeout)."
    except Exception as e:
        return None, f"Lỗi hệ thống khi lấy Chat ID: {str(e)}"

def send_zalo_text(bot_token: str, chat_id: str, message: str):
    """
    Gửi tin nhắn văn bản qua Zalo Bot API.
    """
    if not bot_token or not chat_id:
        print("⚠️ Bỏ qua gửi Zalo do thiếu Token hoặc Chat ID.")
        return False

    url = f"https://bot-api.zapps.me/bot{bot_token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        res = requests.post(url, json=payload, timeout=10)
        
        if res.status_code == 200:
            print("✅ Đã gửi thông báo Zalo thành công!")
            return True
        else:
            print(f"⚠️ Gửi Zalo thất bại: {res.text}")
            return False
            
    except Exception as e:
        print(f"⚠️ Lỗi gửi ZaloBot: {e}")
        return False

def format_sensor_message(data: dict) -> str:
    """Định dạng dữ liệu cảm biến thành tin nhắn dễ đọc."""
    now = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    
    msg = f"📊 THÔNG SỐ NÔNG TRẠI MỚI NHẤT ({now})\n"
    msg += f"--------------------------------\n"
    
    # Nhiệt độ & Độ ẩm không khí
    air_temp = data.get("air_temperature", "N/A")
    air_humi = data.get("air_humidity", "N/A")
    msg += f"🌡️ Không khí: {air_temp}°C | 💧 Ẩm: {air_humi}%\n"
    
    # Đất
    soil_temp = data.get("soil_temperature", "N/A")
    soil_humi = data.get("soil_moisture", "N/A")
    msg += f"🌱 Đất: {soil_temp}°C | 💦 Ẩm đất: {soil_humi}%\n"
    
    # Dinh dưỡng
    ph = data.get("soil_ph", "N/A")
    ec = data.get("ec", "N/A")
    sal = data.get("salinity", "N/A")
    msg += f"🧪 pH: {ph} | ⚡ EC: {ec} µS/cm | 🧂 Mặn: {sal} mg/L\n"
    
    # NPK
    n = data.get("nitrogen", "N/A")
    p = data.get("phosphorus", "N/A")
    k = data.get("potassium", "N/A")
    msg += f"🥩 N-P-K: {n} - {p} - {k} (mg/kg)\n"
    
    # Ánh sáng
    light = data.get("light_intensity", "N/A")
    msg += f"☀️ Ánh sáng: {light} lux\n"
    
    return msg
