#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <Preferences.h>
#include <stdlib.h>
#include <string.h>

//================ PIN CONFIG =================
#define LORA_RX 26
#define LORA_TX 27

#define I2C_SDA 21
#define I2C_SCL 22

#define LCD_ADDR 0x27
#define LCD_COLS 20
#define LCD_ROWS 4

#define LORA_BAUD 9600

// Nut nhan
#define BTN_MODE 32
#define BTN_UP   33
#define BTN_DOWN 25

// Cong tac gat che do
#define SW_MODE 4

// Relay
#define RELAY_HEATER 14
#define RELAY_FAN    12
#define RELAY_PUMP   13
#define RELAY_MIST   15
#define RELAY_LIGHT  2  // ★ THÊM RELAY ĐÈN

//================ RELAY LOGIC =================
#define RELAY_ON  HIGH
#define RELAY_OFF LOW

//================ TIMEOUT =================
static const unsigned long NODE_TIMEOUT_MS = 15000;

//================ BUFFER =================
static const size_t LORA_BUFFER_SIZE = 128;
static const size_t SERIAL_CMD_BUFFER_SIZE = 64;

//================ OBJECTS =================
HardwareSerial LORA(1);
LiquidCrystal_I2C lcd(LCD_ADDR, LCD_COLS, LCD_ROWS);
Preferences prefs;

//================ DATA STRUCT =================
struct SensorData
{
  float airTemp;
  float airHumi;
  float soilTemp;
  float soilHumi;
  int salinity;
  int ec;
  int nitrogen;
  int phosphorus;
  int potassium;
  float ph;
};

struct Settings
{
  float tempLow;
  float tempHigh;

  float airHumiLow;
  float airHumiHigh;

  float soilHumiLow;
  float soilHumiHigh;
};

//================ DEFAULT SETTINGS =================
Settings cfg = {
  20.0,  // tempLow
  30.0,  // tempHigh
  60.0,  // airHumiLow
  75.0,  // airHumiHigh
  40.0,  // soilHumiLow
  55.0   // soilHumiHigh
};

SensorData currentData = {0};

//================ STATE =================
char loraBuffer[LORA_BUFFER_SIZE];
size_t loraIndex = 0;
bool isReceivingPacket = false;
bool hasValidData = false;

unsigned long lastNodeTime = 0;

//================ SERIAL CMD BUFFER ===== ★ MỚI =====
char serialCmdBuffer[SERIAL_CMD_BUFFER_SIZE];
size_t serialCmdIndex = 0;

//================ OUTPUT STATE =================
bool heaterState = false;
bool fanState    = false;
bool pumpState   = false;
bool mistState   = false;
bool lightState  = false;  // ★ MỚI

//================ WEB CONTROL MODE ===== ★ MỚI =====
bool webControlMode = false;  // true = web dang dieu khien

//================ DISPLAY PAGE =================
uint8_t displayPage = 0;

//================ MENU STATE =================
enum MenuItem
{
  MENU_VIEW = 0,
  MENU_TEMP_LOW,
  MENU_TEMP_HIGH,
  MENU_AIR_HUMI_LOW,
  MENU_AIR_HUMI_HIGH,
  MENU_SOIL_HUMI_LOW,
  MENU_SOIL_HUMI_HIGH,
  MENU_SAVE_EXIT
};

MenuItem menuState = MENU_VIEW;
bool inMenu = false;

//================ BUTTON STATE =================
bool lastModeReading = HIGH;
bool lastUpReading   = HIGH;
bool lastDownReading = HIGH;

unsigned long lastModeMs = 0;
unsigned long lastUpMs   = 0;
unsigned long lastDownMs = 0;

const unsigned long DEBOUNCE_MS = 30;

//================ UTIL =================
void relayWrite(uint8_t pin, bool on)
{
  digitalWrite(pin, on ? RELAY_ON : RELAY_OFF);
}

bool isNumericToken(const char* token)
{
  if (token == nullptr || *token == '\0') return false;
  char* endPtr;
  strtod(token, &endPtr);
  return (*endPtr == '\0');
}

bool isAutoMode()
{
  return digitalRead(SW_MODE) == HIGH;
}

//================ SETTINGS =================
void loadSettings()
{
  prefs.begin("gateway_cfg", true);
  cfg.tempLow      = prefs.getFloat("tempLow", 20.0);
  cfg.tempHigh     = prefs.getFloat("tempHigh", 30.0);
  cfg.airHumiLow   = prefs.getFloat("airLow", 60.0);
  cfg.airHumiHigh  = prefs.getFloat("airHigh", 75.0);
  cfg.soilHumiLow  = prefs.getFloat("soilLow", 40.0);
  cfg.soilHumiHigh = prefs.getFloat("soilHigh", 55.0);
  prefs.end();

  if (cfg.tempLow >= cfg.tempHigh)     { cfg.tempLow = 20.0; cfg.tempHigh = 30.0; }
  if (cfg.airHumiLow >= cfg.airHumiHigh) { cfg.airHumiLow = 60.0; cfg.airHumiHigh = 75.0; }
  if (cfg.soilHumiLow >= cfg.soilHumiHigh) { cfg.soilHumiLow = 40.0; cfg.soilHumiHigh = 55.0; }
}

void saveSettings()
{
  prefs.begin("gateway_cfg", false);
  prefs.putFloat("tempLow", cfg.tempLow);
  prefs.putFloat("tempHigh", cfg.tempHigh);
  prefs.putFloat("airLow", cfg.airHumiLow);
  prefs.putFloat("airHigh", cfg.airHumiHigh);
  prefs.putFloat("soilLow", cfg.soilHumiLow);
  prefs.putFloat("soilHigh", cfg.soilHumiHigh);
  prefs.end();
}

//================ PARSE DATA =================
bool parseDataPacket(const char* packet, SensorData& outData)
{
  if (packet == nullptr) return false;

  size_t len = strlen(packet);
  if (len < 3) return false;
  if (packet[0] != '<' || packet[len - 1] != '>') return false;

  char temp[LORA_BUFFER_SIZE];
  strncpy(temp, packet + 1, sizeof(temp) - 1);
  temp[sizeof(temp) - 1] = '\0';

  size_t innerLen = strlen(temp);
  if (innerLen == 0) return false;

  if (temp[innerLen - 1] == '>')
    temp[innerLen - 1] = '\0';
  else
    return false;

  const int EXPECTED_FIELDS = 10;
  char* tokens[EXPECTED_FIELDS] = {0};

  int fieldCount = 0;
  char* savePtr = nullptr;
  char* token = strtok_r(temp, ",", &savePtr);

  while (token != nullptr && fieldCount < EXPECTED_FIELDS)
  {
    tokens[fieldCount++] = token;
    token = strtok_r(nullptr, ",", &savePtr);
  }

  if (fieldCount != EXPECTED_FIELDS || token != nullptr) return false;

  for (int i = 0; i < EXPECTED_FIELDS; i++)
  {
    if (!isNumericToken(tokens[i])) return false;
  }

  outData.airTemp    = atof(tokens[0]);
  outData.airHumi    = atof(tokens[1]);
  outData.soilTemp   = atof(tokens[2]);
  outData.soilHumi   = atof(tokens[3]);
  outData.salinity   = atoi(tokens[4]);
  outData.ec         = atoi(tokens[5]);
  outData.nitrogen   = atoi(tokens[6]);
  outData.phosphorus = atoi(tokens[7]);
  outData.potassium  = atoi(tokens[8]);
  outData.ph         = atof(tokens[9]);

  return true;
}

//================ ★ SERIAL COMMAND HANDLER ★ =================
// Format: RELAY:NAME:ON  hoặc  RELAY:NAME:OFF
// Vi du: RELAY:HEATER:ON, RELAY:FAN:OFF, RELAY:LIGHT:ON
void handleSerialCommand(const char* cmd)
{
  Serial.print(">> CMD: ");
  Serial.println(cmd);

  // Parse RELAY:NAME:STATE
  if (strncmp(cmd, "RELAY:", 6) != 0)
  {
    Serial.println(">> Unknown command");
    return;
  }

  char cmdCopy[SERIAL_CMD_BUFFER_SIZE];
  strncpy(cmdCopy, cmd + 6, sizeof(cmdCopy) - 1);
  cmdCopy[sizeof(cmdCopy) - 1] = '\0';

  // Tìm dấu ':'
  char* colon = strchr(cmdCopy, ':');
  if (colon == nullptr)
  {
    Serial.println(">> Invalid format");
    return;
  }

  *colon = '\0';
  char* relayName = cmdCopy;
  char* stateStr = colon + 1;

  bool state = (strcmp(stateStr, "ON") == 0);

  // Map relay name -> pin & state
  if (strcmp(relayName, "HEATER") == 0)
  {
    heaterState = state;
    relayWrite(RELAY_HEATER, heaterState);
    webControlMode = true;
  }
  else if (strcmp(relayName, "FAN") == 0)
  {
    fanState = state;
    relayWrite(RELAY_FAN, fanState);
    webControlMode = true;
  }
  else if (strcmp(relayName, "PUMP") == 0)
  {
    pumpState = state;
    relayWrite(RELAY_PUMP, pumpState);
    webControlMode = true;
  }
  else if (strcmp(relayName, "MIST") == 0)
  {
    mistState = state;
    relayWrite(RELAY_MIST, mistState);
    webControlMode = true;
  }
  else if (strcmp(relayName, "LIGHT") == 0)
  {
    lightState = state;
    relayWrite(RELAY_LIGHT, lightState);
    webControlMode = true;
  }
  else
  {
    Serial.print(">> Unknown relay: ");
    Serial.println(relayName);
    return;
  }

  Serial.print(">> OK: ");
  Serial.print(relayName);
  Serial.print(" = ");
  Serial.println(state ? "ON" : "OFF");
}

void readSerialCommands()
{
  while (Serial.available())
  {
    char c = (char)Serial.read();

    if (c == '\n' || c == '\r')
    {
      if (serialCmdIndex > 0)
      {
        serialCmdBuffer[serialCmdIndex] = '\0';
        handleSerialCommand(serialCmdBuffer);
        serialCmdIndex = 0;
      }
    }
    else
    {
      if (serialCmdIndex < (SERIAL_CMD_BUFFER_SIZE - 1))
      {
        serialCmdBuffer[serialCmdIndex++] = c;
      }
      else
      {
        serialCmdIndex = 0; // overflow, reset
      }
    }
  }
}

//================ LCD =================
void displayPage1(const SensorData& d)
{
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Ta:");  lcd.print(d.airTemp, 1);
  lcd.print("C  Ha:");  lcd.print(d.airHumi, 0); lcd.print("%");

  lcd.setCursor(0, 1);
  lcd.print("Ts:");  lcd.print(d.soilTemp, 1);
  lcd.print("C  Hs:");  lcd.print(d.soilHumi, 0); lcd.print("%");

  lcd.setCursor(0, 2);
  lcd.print("EC:");  lcd.print(d.ec);

  lcd.setCursor(0, 3);
  lcd.print("Sal:");  lcd.print(d.salinity);

  lcd.setCursor(17, 0);  lcd.print("[1]");
}

void displayPage2(const SensorData& d)
{
  lcd.clear();
  lcd.setCursor(0, 0);  lcd.print("N:");  lcd.print(d.nitrogen);
  lcd.setCursor(0, 1);  lcd.print("P:");  lcd.print(d.phosphorus);
  lcd.setCursor(0, 2);  lcd.print("K:");  lcd.print(d.potassium);
  lcd.setCursor(0, 3);  lcd.print("pH:");  lcd.print(d.ph, 1);
  lcd.setCursor(17, 0);  lcd.print("[2]");
}

void updateDisplay()
{
  if (!hasValidData)
  {
    lcd.clear();
    lcd.setCursor(0, 0);  lcd.print("Waiting data...");
    lcd.setCursor(0, 1);  lcd.print("Press MODE menu");
    lcd.setCursor(17, 0);
    lcd.print(displayPage == 0 ? "[1]" : "[2]");
    return;
  }

  if (displayPage == 0)  displayPage1(currentData);
  else  displayPage2(currentData);
}

void displayNodeDisconnected()
{
  lcd.clear();
  lcd.setCursor(0, 0);  lcd.print("Node disconnected");
  lcd.setCursor(0, 1);  lcd.print("No recent data");
  lcd.setCursor(0, 2);  lcd.print("All outputs OFF");
  lcd.setCursor(0, 3);  lcd.print("Press MODE menu");
}

void displayMenu()
{
  lcd.clear();

  switch (menuState)
  {
    case MENU_TEMP_LOW:
      lcd.setCursor(0, 0); lcd.print("SET TEMP LOW");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.tempLow, 1); lcd.print(" C");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_TEMP_HIGH:
      lcd.setCursor(0, 0); lcd.print("SET TEMP HIGH");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.tempHigh, 1); lcd.print(" C");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_AIR_HUMI_LOW:
      lcd.setCursor(0, 0); lcd.print("SET AIR HUMI LOW");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.airHumiLow, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_AIR_HUMI_HIGH:
      lcd.setCursor(0, 0); lcd.print("SET AIR HUMI HIGH");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.airHumiHigh, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_SOIL_HUMI_LOW:
      lcd.setCursor(0, 0); lcd.print("SET SOIL HUMI LOW");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.soilHumiLow, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_SOIL_HUMI_HIGH:
      lcd.setCursor(0, 0); lcd.print("SET SOIL HUMI HIGH");
      lcd.setCursor(0, 1); lcd.print("Value: "); lcd.print(cfg.soilHumiHigh, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case MENU_SAVE_EXIT:
      lcd.setCursor(0, 0); lcd.print("SAVE & EXIT ?");
      lcd.setCursor(0, 1); lcd.print("UP = Save");
      lcd.setCursor(0, 2); lcd.print("DOWN = Exit");
      lcd.setCursor(0, 3); lcd.print("MODE = Next");
      break;
    default: break;
  }
}

//================ BUTTON =================
bool readButtonEdge(uint8_t pin, bool &lastReading, unsigned long &lastTime)
{
  bool reading = digitalRead(pin);
  if (reading != lastReading)
  {
    if (millis() - lastTime > DEBOUNCE_MS)
    {
      lastTime = millis();
      lastReading = reading;
      if (reading == LOW) return true;
    }
  }
  return false;
}

bool modePressed() { return readButtonEdge(BTN_MODE, lastModeReading, lastModeMs); }
bool upPressed() { return readButtonEdge(BTN_UP, lastUpReading, lastUpMs); }
bool downPressed() { return readButtonEdge(BTN_DOWN, lastDownReading, lastDownMs); }

void enterMenu() { inMenu = true; menuState = MENU_TEMP_LOW; displayMenu(); }
void exitMenu() { inMenu = false; menuState = MENU_VIEW; updateDisplay(); }

void increaseValue()
{
  switch (menuState)
  {
    case MENU_TEMP_LOW:
      cfg.tempLow += 0.5;
      if (cfg.tempLow >= cfg.tempHigh) cfg.tempLow = cfg.tempHigh - 0.5;
      break;
    case MENU_TEMP_HIGH:
      cfg.tempHigh += 0.5;
      if (cfg.tempHigh <= cfg.tempLow) cfg.tempHigh = cfg.tempLow + 0.5;
      break;
    case MENU_AIR_HUMI_LOW:
      cfg.airHumiLow += 1.0;
      if (cfg.airHumiLow > 100.0) cfg.airHumiLow = 100.0;
      if (cfg.airHumiLow >= cfg.airHumiHigh) cfg.airHumiLow = cfg.airHumiHigh - 1.0;
      break;
    case MENU_AIR_HUMI_HIGH:
      cfg.airHumiHigh += 1.0;
      if (cfg.airHumiHigh > 100.0) cfg.airHumiHigh = 100.0;
      if (cfg.airHumiHigh <= cfg.airHumiLow) cfg.airHumiHigh = cfg.airHumiLow + 1.0;
      break;
    case MENU_SOIL_HUMI_LOW:
      cfg.soilHumiLow += 1.0;
      if (cfg.soilHumiLow > 100.0) cfg.soilHumiLow = 100.0;
      if (cfg.soilHumiLow >= cfg.soilHumiHigh) cfg.soilHumiLow = cfg.soilHumiHigh - 1.0;
      break;
    case MENU_SOIL_HUMI_HIGH:
      cfg.soilHumiHigh += 1.0;
      if (cfg.soilHumiHigh > 100.0) cfg.soilHumiHigh = 100.0;
      if (cfg.soilHumiHigh <= cfg.soilHumiLow) cfg.soilHumiHigh = cfg.soilHumiLow + 1.0;
      break;
    case MENU_SAVE_EXIT:
      saveSettings(); exitMenu(); return;
    default: break;
  }
  displayMenu();
}

void decreaseValue()
{
  switch (menuState)
  {
    case MENU_TEMP_LOW:
      cfg.tempLow -= 0.5;
      if (cfg.tempLow < 0.0) cfg.tempLow = 0.0;
      if (cfg.tempLow >= cfg.tempHigh) cfg.tempLow = cfg.tempHigh - 0.5;
      break;
    case MENU_TEMP_HIGH:
      cfg.tempHigh -= 0.5;
      if (cfg.tempHigh < 0.5) cfg.tempHigh = 0.5;
      if (cfg.tempHigh <= cfg.tempLow) cfg.tempHigh = cfg.tempLow + 0.5;
      break;
    case MENU_AIR_HUMI_LOW:
      cfg.airHumiLow -= 1.0;
      if (cfg.airHumiLow < 0.0) cfg.airHumiLow = 0.0;
      break;
    case MENU_AIR_HUMI_HIGH:
      cfg.airHumiHigh -= 1.0;
      if (cfg.airHumiHigh < 1.0) cfg.airHumiHigh = 1.0;
      if (cfg.airHumiHigh <= cfg.airHumiLow) cfg.airHumiHigh = cfg.airHumiLow + 1.0;
      break;
    case MENU_SOIL_HUMI_LOW:
      cfg.soilHumiLow -= 1.0;
      if (cfg.soilHumiLow < 0.0) cfg.soilHumiLow = 0.0;
      break;
    case MENU_SOIL_HUMI_HIGH:
      cfg.soilHumiHigh -= 1.0;
      if (cfg.soilHumiHigh < 1.0) cfg.soilHumiHigh = 1.0;
      if (cfg.soilHumiHigh <= cfg.soilHumiLow) cfg.soilHumiHigh = cfg.soilHumiLow + 1.0;
      break;
    case MENU_SAVE_EXIT:
      exitMenu(); return;
    default: break;
  }
  displayMenu();
}

void nextMenuItem()
{
  if (!inMenu) { enterMenu(); return; }
  if (menuState == MENU_SAVE_EXIT) menuState = MENU_TEMP_LOW;
  else menuState = (MenuItem)((int)menuState + 1);
  displayMenu();
}

void handleButtons()
{
  if (modePressed())
  {
    // Bấm MODE khi đang ở web control → tắt web control, về auto/manual
    if (webControlMode && !inMenu) webControlMode = false;
    nextMenuItem();
  }

  if (!inMenu)
  {
    if (upPressed())
    {
      displayPage++;
      if (displayPage > 1) displayPage = 0;
      updateDisplay();
    }
    return;
  }

  if (upPressed()) increaseValue();
  if (downPressed()) decreaseValue();
}

//================ AUTO CONTROL =================
void applyOutputs()
{
  relayWrite(RELAY_HEATER, heaterState);
  relayWrite(RELAY_FAN, fanState);
  relayWrite(RELAY_PUMP, pumpState);
  relayWrite(RELAY_MIST, mistState);
  relayWrite(RELAY_LIGHT, lightState);
}

void controlOutputsAuto(const SensorData& data)
{
  // Khong dieu khien auto khi web dang control
  if (webControlMode) return;

  if (data.airTemp < cfg.tempLow)      { heaterState = true; fanState = false; }
  else if (data.airTemp > cfg.tempHigh) { heaterState = false; fanState = true; }

  if (data.airHumi < cfg.airHumiLow)       mistState = true;
  else if (data.airHumi > cfg.airHumiHigh)  mistState = false;

  if (data.soilHumi < cfg.soilHumiLow)      pumpState = true;
  else if (data.soilHumi > cfg.soilHumiHigh) pumpState = false;

  applyOutputs();
}

void turnOffAllOutputs()
{
  heaterState = false;
  fanState = false;
  pumpState = false;
  mistState = false;
  lightState = false;
  applyOutputs();
}

//================ NODE TIMEOUT =================
void checkNodeTimeout()
{
  if (hasValidData && (millis() - lastNodeTime > NODE_TIMEOUT_MS))
  {
    hasValidData = false;
    if (!webControlMode) turnOffAllOutputs();
    displayNodeDisconnected();
  }
}

//================ LORA =================
void resetLoRaBuffer()
{
  memset(loraBuffer, 0, sizeof(loraBuffer));
  loraIndex = 0;
  isReceivingPacket = false;
}

void handleLoRaChar(char c)
{
  if (c == '<') { resetLoRaBuffer(); isReceivingPacket = true; }
  if (!isReceivingPacket) return;
  if (loraIndex >= (LORA_BUFFER_SIZE - 1)) { resetLoRaBuffer(); return; }

  loraBuffer[loraIndex++] = c;
  loraBuffer[loraIndex] = '\0';

  if (c == '>')
  {
    SensorData parsedData;
    if (parseDataPacket(loraBuffer, parsedData))
    {
      currentData = parsedData;
      hasValidData = true;
      lastNodeTime = millis();

      // Print data for serial_bridge.py
      Serial.println("===== DATA NODE =====");
      Serial.print("Air Temp: "); Serial.println(currentData.airTemp);
      Serial.print("Air Humi: "); Serial.println(currentData.airHumi);
      Serial.print("Soil Temp: "); Serial.println(currentData.soilTemp);
      Serial.print("Soil Humi: "); Serial.println(currentData.soilHumi);
      Serial.print("Salinity: "); Serial.println(currentData.salinity);
      Serial.print("EC: "); Serial.println(currentData.ec);
      Serial.print("N: "); Serial.println(currentData.nitrogen);
      Serial.print("P: "); Serial.println(currentData.phosphorus);
      Serial.print("K: "); Serial.println(currentData.potassium);
      Serial.print("pH: "); Serial.println(currentData.ph);
      Serial.println("=====================");

      if (isAutoMode() && !webControlMode)
      {
        controlOutputsAuto(currentData);
      }

      if (!inMenu) updateDisplay();
    }
    resetLoRaBuffer();
  }
}

//================ SETUP =================
void setupPins()
{
  pinMode(BTN_MODE, INPUT_PULLUP);
  pinMode(BTN_UP, INPUT_PULLUP);
  pinMode(BTN_DOWN, INPUT_PULLUP);
  pinMode(SW_MODE, INPUT_PULLUP);

  pinMode(RELAY_HEATER, OUTPUT);
  pinMode(RELAY_FAN, OUTPUT);
  pinMode(RELAY_PUMP, OUTPUT);
  pinMode(RELAY_MIST, OUTPUT);
  pinMode(RELAY_LIGHT, OUTPUT);

  turnOffAllOutputs();
}

void setup()
{
  Serial.begin(115200);
  setupPins();
  loadSettings();

  Wire.begin(I2C_SDA, I2C_SCL);

  lcd.init();
  lcd.backlight();

  lcd.clear();
  lcd.setCursor(0, 0);  lcd.print("LoRa Gateway v2");
  lcd.setCursor(0, 1);  lcd.print("Web Control Ready");
  lcd.setCursor(0, 2);  lcd.print("UP: Change Page");
  lcd.setCursor(0, 3);  lcd.print("MODE: Settings");

  LORA.begin(LORA_BAUD, SERIAL_8N1, LORA_RX, LORA_TX, false, 256);
  resetLoRaBuffer();
  memset(serialCmdBuffer, 0, sizeof(serialCmdBuffer));

  delay(1200);
  updateDisplay();
}

void loop()
{
  handleButtons();

  // ★ Đọc lệnh từ Serial (serial_bridge.py gửi xuống)
  readSerialCommands();

  if (!isAutoMode() && !webControlMode)
  {
    turnOffAllOutputs();
  }

  if (LORA.available() > 0)
  {
    char c = (char)LORA.read();
    handleLoRaChar(c);
  }

  checkNodeTimeout();
}
