<p align="center">
  <img src="https://img.shields.io/badge/ESP32-IoT-blue?style=for-the-badge&logo=espressif&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Next.js-Frontend-black?style=for-the-badge&logo=next.js&logoColor=white" />
  <img src="https://img.shields.io/badge/Gemini_AI-Analysis-8E75B2?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/LoRa-Wireless-FF6F00?style=for-the-badge" />
</p>

<h1 align="center">🌱 HỆ THỐNG GIÁM SÁT NÔNG TRẠI THÔNG MINH</h1>
<h3 align="center">Smart Farm Monitoring & Auto-Control System</h3>

<p align="center">
  <i>Hệ thống IoT giám sát môi trường nông nghiệp real-time với điều khiển tự động relay, phân tích AI, và dashboard web hiện đại.</i>
</p>

---

## 📋 Mục Lục

- [✨ Tính Năng](#-tính-năng)
- [🏗️ Kiến Trúc Hệ Thống](#️-kiến-trúc-hệ-thống)
- [🛠️ Công Nghệ](#️-công-nghệ)
- [📦 Cấu Trúc Dự Án](#-cấu-trúc-dự-án)
- [🚀 Cài Đặt & Chạy](#-cài-đặt--chạy)
- [🎛️ Điều Khiển Thiết Bị](#️-điều-khiển-thiết-bị)
- [⚙️ Cài Đặt Ngưỡng Tự Động](#️-cài-đặt-ngưỡng-tự-động)
- [🔌 Sơ Đồ Nối Dây](#-sơ-đồ-nối-dây)
- [📡 API Endpoints](#-api-endpoints)

---

## ✨ Tính Năng

### 📊 Giám Sát Real-Time
- **10 thông số cảm biến**: Nhiệt độ KK, Độ ẩm KK, Nhiệt độ đất, Độ ẩm đất, pH, EC, N-P-K, Độ mặn, Ánh sáng
- **Biểu đồ real-time** với animation mượt mà
- **Cập nhật tức thì** qua WebSocket
- **Đánh giá trạng thái** (Tốt / Cảnh báo / Nguy hiểm) cho từng thông số

### 🤖 Điều Khiển Tự Động
- **Auto Mode**: Tự bật/tắt relay dựa trên ngưỡng cảm biến
- **Manual Mode**: Điều khiển tay từng relay qua LCD hoặc web
- **Ngưỡng tùy chỉnh**: Set ngưỡng bật/tắt từ web HOẶC trên LCD ESP32
- **Đồng bộ 2 chiều**: ESP32 ↔ Web — chỉnh bên nào cũng cập nhật bên kia

### 🔄 Đồng Bộ ESP32 ↔ Web
| Hướng | Dữ liệu | Cách hoạt động |
|-------|---------|----------------|
| ESP32 → Web | Sensor data | LoRa → Gateway → Serial → Bridge → API → WebSocket |
| ESP32 → Web | Ngưỡng settings | LCD Save → `CFG:` Serial → Bridge → API |
| ESP32 → Web | Relay ON/OFF | Manual menu → `RELAY_STATE:` Serial → Bridge → API |
| Web → ESP32 | Relay commands | Dashboard → API → Queue → Bridge → `RELAY:` Serial |
| Web → ESP32 | Ngưỡng settings | Dashboard → API → Queue → Bridge → `CFG:` Serial |

### 🧠 Phân Tích AI
- Tích hợp **Google Gemini AI** phân tích tổng quan tình trạng đất & môi trường
- Đưa ra **khuyến nghị cụ thể** cho từng loại cây trồng

### 🎨 Giao Diện Premium
- **Dark mode** với gradient hiện đại
- **Responsive** — hoạt động trên mọi thiết bị
- **Micro-animations** — hiệu ứng mượt mà
- **Real-time charts** với cập nhật trực tiếp

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────────┐     LoRa 433MHz     ┌─────────────────────┐
│  SENSOR NODE    │ ──────────────────▶  │  GATEWAY ESP32      │
│  (ESP32 #1)     │                      │  • LCD 20x4         │
│  • DHT22        │                      │  • 3 Buttons        │
│  • Soil sensors │                      │  • 4 Relay outputs  │
│  • NPK sensor   │                      │  • Menu system      │
│  • pH sensor    │                      └──────┬──────────────┘
│  • Light sensor │                             │ USB Serial
└─────────────────┘                             │ 115200 baud
                                                ▼
                                   ┌────────────────────────┐
                                   │  SERIAL BRIDGE (Python) │
                                   │  serial_bridge.py       │
                                   │  • Parse sensor data    │
                                   │  • Sync settings ↕      │
                                   │  • Sync relay states ↕  │
                                   └────────┬───────────────┘
                                            │ HTTP REST API
                                            ▼
                              ┌──────────────────────────────┐
                              │  BACKEND (FastAPI + Python)   │
                              │  main.py                      │
                              │  • REST API endpoints         │
                              │  • WebSocket broadcast        │
                              │  • Auto-control engine        │
                              │  • Gemini AI analysis         │
                              └──────────┬───────────────────┘
                                         │ WebSocket + HTTP
                                         ▼
                              ┌──────────────────────────────┐
                              │  FRONTEND (Next.js + React)   │
                              │  • Real-time dashboard        │
                              │  • Sensor cards + charts      │
                              │  • Control panel              │
                              │  • AI analysis view           │
                              └──────────────────────────────┘
```

---

## 🛠️ Công Nghệ

### Hardware
| Thành phần | Mô tả |
|-----------|-------|
| **ESP32** (x2) | Vi điều khiển chính — 1 node cảm biến, 1 gateway |
| **LoRa SX1278** | Truyền dữ liệu không dây 433MHz, tầm xa ~1km |
| **LCD 20x4 I2C** | Hiển thị data + menu cài đặt trên gateway |
| **DHT22** | Cảm biến nhiệt độ & độ ẩm không khí |
| **Soil Moisture** | Cảm biến độ ẩm đất |
| **NPK Sensor** | Đo Nitrogen, Phosphorus, Potassium |
| **pH Sensor** | Đo độ pH đất |
| **Relay Module** (x4) | Điều khiển: Sưởi, Quạt, Bơm, Phun sương |

### Software
| Stack | Công nghệ |
|-------|-----------|
| **Firmware** | Arduino C++ (ESP32) |
| **Serial Bridge** | Python + PySerial |
| **Backend** | FastAPI + Uvicorn + WebSocket |
| **Frontend** | Next.js 16 + React |
| **AI Engine** | Google Gemini API |
| **Styling** | Vanilla CSS (Dark theme) |

---

## 📦 Cấu Trúc Dự Án

```
Check-thong-so/
├── 📁 esp32/
│   └── sensor_sender.ino       # Firmware gateway ESP32
│
├── 📁 backend/
│   ├── main.py                 # FastAPI server + auto-control
│   ├── serial_bridge.py        # Serial ↔ HTTP bridge
│   ├── test_send_data.py       # Mock data sender (dev/test)
│   ├── test_auto.py            # Auto-control tester
│   ├── requirements.txt        # Python dependencies
│   └── .env                    # GEMINI_API_KEY
│
├── 📁 frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.js         # Main dashboard page
│   │   │   ├── layout.js       # App layout + metadata
│   │   │   └── globals.css     # Design system + all styles
│   │   ├── components/
│   │   │   ├── SensorCard.js   # Sensor display card
│   │   │   ├── ControlPanel.js # Relay control + auto mode
│   │   │   └── AIAnalysis.js   # AI analysis panel
│   │   ├── hooks/
│   │   │   └── useWebSocket.js # WebSocket hook
│   │   └── lib/
│   │       ├── api.js          # API client
│   │       └── sensorConfig.js # Sensor definitions
│   ├── .env.local              # NEXT_PUBLIC_API_URL
│   └── package.json
│
└── README.md                   # 📖 Bạn đang đọc file này
```

---

## 🚀 Cài Đặt & Chạy

### 1. Clone & cài đặt

```bash
git clone https://github.com/your-repo/Check-thong-so.git
cd Check-thong-so
```

### 2. Backend

```bash
cd backend

# Cài dependencies
pip install -r requirements.txt

# Tạo file .env
echo GEMINI_API_KEY=your_api_key_here > .env

# Chạy server
python main.py
```
> 🌐 Backend chạy tại `http://localhost:8000`

### 3. Frontend

```bash
cd frontend

# Cài dependencies
npm install

# Tạo file .env.local
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local

# Chạy dev server
npm run dev
```
> 🖥️ Frontend chạy tại `http://localhost:3000`

### 4. Serial Bridge (khi có ESP32)

```bash
cd backend

# Tự tìm COM port
python serial_bridge.py

# Hoặc chỉ định port
python serial_bridge.py COM5
```

### 5. Test không cần hardware

```bash
cd backend
python test_send_data.py    # Gửi mock sensor data
```

---

## 🎛️ Điều Khiển Thiết Bị

### Trên Web Dashboard
| Chế độ | Mô tả |
|--------|-------|
| 🤖 **TỰ ĐỘNG** | Hệ thống tự bật/tắt relay theo ngưỡng cảm biến |
| 👋 **THỦ CÔNG** | Bấm toggle để bật/tắt từng relay |

### Trên ESP32 (3 nút bấm)
| Nút | Chức năng |
|-----|-----------|
| **MODE** | Vào menu / Chuyển mục |
| **UP** | Tăng giá trị / Chọn ON / Lên |
| **DOWN** | Giảm giá trị / Chọn OFF / Xuống |

### Menu ESP32
```
HOME ──MODE──▶ MAIN MENU
                 ├── AUTO MODE      → Về home, chạy auto
                 ├── MANUAL MODE    → Điều khiển tay relay
                 └── SETTINGS       → Chỉnh ngưỡng
                       ├── TEMP LOW      (Bật sưởi khi dưới)
                       ├── TEMP HIGH     (Bật quạt khi trên)
                       ├── AIR HUMI LOW  (Bật phun sương)
                       ├── AIR HUMI HIGH (Tắt phun sương)
                       ├── SOIL HUMI LOW (Bật bơm)
                       ├── SOIL HUMI HIGH(Tắt bơm)
                       └── SAVE & EXIT
```

---

## ⚙️ Cài Đặt Ngưỡng Tự Động

| Cảm biến | Thiết bị | Điều kiện BẬT | Điều kiện TẮT | Mặc định |
|----------|---------|--------------|--------------|----------|
| 🌡️ Nhiệt độ KK | Sưởi | `< temp_low` | `> temp_low` | 20°C |
| 🌡️ Nhiệt độ KK | Quạt | `> temp_high` | `< temp_high` | 30°C |
| 💨 Độ ẩm KK | Phun sương | `< air_humi_low` | `> air_humi_high` | 60% / 80% |
| 🌱 Độ ẩm đất | Bơm | `< soil_humi_low` | `> soil_humi_high` | 30% / 60% |

> 💡 Chỉnh ngưỡng từ **web** (⚙️ Cài đặt ngưỡng) hoặc từ **LCD** (SETTINGS menu) — đều đồng bộ 2 chiều!

---

## 🔌 Sơ Đồ Nối Dây

### Gateway ESP32

```
ESP32 Pin    →    Thiết bị
─────────────────────────────
GPIO 26      →    LoRa RX
GPIO 27      →    LoRa TX
GPIO 21      →    LCD SDA (I2C)
GPIO 22      →    LCD SCL (I2C)
GPIO 32      →    Nút MODE
GPIO 33      →    Nút UP
GPIO 25      →    Nút DOWN
GPIO 14      →    Relay HEATER
GPIO 12      →    Relay FAN
GPIO 13      →    Relay PUMP
GPIO 15      →    Relay MIST
USB          →    Máy tính (Serial Bridge)
```

---

## 📡 API Endpoints

### Sensor Data
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/sensor-data` | Nhận data từ serial bridge |
| `GET` | `/api/sensor-data/latest` | Lấy data mới nhất |
| `GET` | `/api/sensor-data/history` | Lịch sử data |

### Relay Control
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/relay/status` | Trạng thái các relay |
| `POST` | `/api/relay/control` | Bật/tắt relay từ web |
| `GET` | `/api/relay/pending` | Serial bridge poll commands |
| `POST` | `/api/relay/sync-from-device` | ESP32 → Web relay sync |

### Auto Control
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET` | `/api/auto/status` | Trạng thái auto mode + ngưỡng |
| `POST` | `/api/auto/toggle` | Bật/tắt auto mode |
| `POST` | `/api/auto/thresholds` | Cập nhật ngưỡng (↔ ESP32) |

### AI Analysis
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `POST` | `/api/analysis` | Phân tích AI (Gemini) |

### WebSocket
| Endpoint | Mô tả |
|----------|-------|
| `ws://localhost:8000/ws` | Real-time data broadcast |

---

## 🔐 Biến Môi Trường

### Backend (`backend/.env`)
```env
GEMINI_API_KEY=your_gemini_api_key
```

### Frontend (`frontend/.env.local`)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 👥 Tác Giả

Dự án được phát triển như đồ án hệ thống IoT nông nghiệp thông minh.

---

<p align="center">
  <b>🌾 Smart Farming, Better Future 🌾</b>
</p>
