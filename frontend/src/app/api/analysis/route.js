// Next.js API Route — Gọi Gemini từ server (key KHÔNG lộ ra browser)
import { NextResponse } from "next/server";

const MODELS = [
  { id: "gemma-3-27b-it", name: "Gemma 3 27B" },
  { id: "gemini-2.0-flash", name: "Gemini 2.0 Flash" },
  { id: "gemma-3-12b-it", name: "Gemma 3 12B" },
  { id: "gemma-3-4b-it", name: "Gemma 3 4B" },
];

const BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models";

export async function POST(request) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "GEMINI_API_KEY chưa được cấu hình trong .env" },
      { status: 500 }
    );
  }

  const { sensor_data } = await request.json();
  if (!sensor_data) {
    return NextResponse.json({ error: "Thiếu sensor_data" }, { status: 400 });
  }

  const prompt = `Bạn là chuyên gia nông nghiệp thông minh. Phân tích dữ liệu cảm biến nhà kính sau và đưa ra đánh giá + khuyến nghị ngắn gọn bằng tiếng Việt:

📊 Dữ liệu:
- Nhiệt độ không khí: ${sensor_data.air_temperature ?? "N/A"}°C
- Độ ẩm không khí: ${sensor_data.air_humidity ?? "N/A"}%
- Nhiệt độ đất: ${sensor_data.soil_temperature ?? "N/A"}°C
- Độ ẩm đất: ${sensor_data.soil_moisture ?? "N/A"}%
- pH đất: ${sensor_data.soil_ph ?? "N/A"}
- EC (độ dẫn điện): ${sensor_data.ec ?? "N/A"} µS/cm
- Độ mặn: ${sensor_data.salinity ?? "N/A"}
- Nitrogen (N): ${sensor_data.nitrogen ?? "N/A"} mg/kg
- Phosphorus (P): ${sensor_data.phosphorus ?? "N/A"} mg/kg
- Potassium (K): ${sensor_data.potassium ?? "N/A"} mg/kg

Trả lời theo format:
🌡️ ĐÁNH GIÁ TỔNG QUAN: (1-2 câu)
⚠️ CẢNH BÁO: (nếu có thông số bất thường)
💡 KHUYẾN NGHỊ: (3-5 gợi ý cụ thể)
🌱 ĐÁNH GIÁ CÂY TRỒNG: (phù hợp trồng gì)`;

  const body = JSON.stringify({
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { temperature: 0.7, maxOutputTokens: 1000 },
  });

  // Thử từng model, model nào trả lời được thì dùng
  for (const model of MODELS) {
    try {
      const url = `${BASE_URL}/${model.id}:generateContent?key=${apiKey}`;
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      if (res.status === 503 || res.status === 429) {
        console.warn(`⚠️ ${model.name} quá tải, thử model tiếp...`);
        continue;
      }

      if (!res.ok) {
        const errText = await res.text();
        console.error(`${model.name} lỗi:`, errText.slice(0, 200));
        continue;
      }

      const data = await res.json();
      const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
      if (!text) continue;

      return NextResponse.json({
        text,
        modelName: model.name,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      console.warn(`⚠️ ${model.name} failed:`, err.message);
      continue;
    }
  }

  return NextResponse.json(
    { error: "Tất cả model đều quá tải. Vui lòng thử lại sau 1 phút." },
    { status: 503 }
  );
}
