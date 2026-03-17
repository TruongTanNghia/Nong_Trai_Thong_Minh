// Sensor configuration: thresholds, icons, labels for all 11 parameters
const SENSOR_CONFIG = {
  soil_temperature: {
    label: "Nhiệt độ đất",
    unit: "°C",
    icon: "🌡️",
    min: 0,
    max: 50,
    normalRange: [15, 30],
    warningRange: [10, 35],
  },
  soil_moisture: {
    label: "Độ ẩm đất",
    unit: "%",
    icon: "💧",
    min: 0,
    max: 100,
    normalRange: [30, 70],
    warningRange: [20, 80],
  },
  soil_ph: {
    label: "pH đất",
    unit: "",
    icon: "⚗️",
    min: 0,
    max: 14,
    normalRange: [5.5, 7.5],
    warningRange: [4.5, 8.5],
  },
  ec: {
    label: "EC (Độ dẫn điện)",
    unit: "µS/cm",
    icon: "⚡",
    min: 0,
    max: 2000,
    normalRange: [200, 800],
    warningRange: [100, 1200],
  },
  nitrogen: {
    label: "Nitrogen (N)",
    unit: "mg/kg",
    icon: "🟢",
    min: 0,
    max: 200,
    normalRange: [20, 100],
    warningRange: [10, 150],
  },
  phosphorus: {
    label: "Phosphorus (P)",
    unit: "mg/kg",
    icon: "🟡",
    min: 0,
    max: 200,
    normalRange: [10, 80],
    warningRange: [5, 120],
  },
  potassium: {
    label: "Potassium (K)",
    unit: "mg/kg",
    icon: "🟠",
    min: 0,
    max: 300,
    normalRange: [50, 200],
    warningRange: [30, 250],
  },
  salinity: {
    label: "Độ mặn",
    unit: "mg/L",
    icon: "🧂",
    min: 0,
    max: 1000,
    normalRange: [0, 200],
    warningRange: [0, 400],
  },
  air_temperature: {
    label: "Nhiệt độ không khí",
    unit: "°C",
    icon: "🌤️",
    min: -10,
    max: 50,
    normalRange: [20, 32],
    warningRange: [15, 38],
  },
  air_humidity: {
    label: "Độ ẩm không khí",
    unit: "%",
    icon: "💨",
    min: 0,
    max: 100,
    normalRange: [40, 80],
    warningRange: [25, 90],
  },
  light_intensity: {
    label: "Cường độ ánh sáng",
    unit: "lux",
    icon: "☀️",
    min: 0,
    max: 100000,
    normalRange: [5000, 60000],
    warningRange: [1000, 80000],
  },
};

export function getSensorConfig(key) {
  return SENSOR_CONFIG[key] || null;
}

export function getAllSensorKeys() {
  return Object.keys(SENSOR_CONFIG);
}

export function getStatus(key, value) {
  if (value === null || value === undefined) return "none";
  const config = SENSOR_CONFIG[key];
  if (!config) return "none";

  const [normalMin, normalMax] = config.normalRange;
  const [warnMin, warnMax] = config.warningRange;

  if (value >= normalMin && value <= normalMax) return "normal";
  if (value >= warnMin && value <= warnMax) return "warning";
  return "danger";
}

export function getStatusLabel(status) {
  switch (status) {
    case "normal": return "Tốt";
    case "warning": return "Lưu ý";
    case "danger": return "Cảnh báo";
    default: return "N/A";
  }
}

export function getRangePercent(key, value) {
  if (value === null || value === undefined) return 0;
  const config = SENSOR_CONFIG[key];
  if (!config) return 0;
  return Math.min(100, Math.max(0, ((value - config.min) / (config.max - config.min)) * 100));
}

export function formatValue(value) {
  if (value === null || value === undefined) return "--";
  if (typeof value === "number") {
    if (value >= 10000) return value.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
    if (Number.isInteger(value)) return value.toString();
    return value.toFixed(1);
  }
  return String(value);
}
