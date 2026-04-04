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

// Relay
#define RELAY_HEATER 14
#define RELAY_FAN    12
#define RELAY_PUMP   13
#define RELAY_MIST   15
#define RELAY_LIGHT  16

//================ RELAY LOGIC =================
#define RELAY_ON  HIGH
#define RELAY_OFF LOW

//================ TIMEOUT =================
static const unsigned long NODE_TIMEOUT_MS = 15000;

//================ BUFFER =================
static const size_t LORA_BUFFER_SIZE = 128;
static const size_t SERIAL_CMD_BUFFER_SIZE = 200;

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
static const Settings DEFAULT_CFG = {
  20.0,
  30.0,
  60.0,
  80.0,
  30.0,
  60.0
};

Settings cfg = DEFAULT_CFG;
SensorData currentData = {0};

//================ STATE =================
char loraBuffer[LORA_BUFFER_SIZE];
size_t loraIndex = 0;
bool isReceivingPacket = false;
bool hasValidData = false;
unsigned long lastNodeTime = 0;

char serialCmdBuffer[SERIAL_CMD_BUFFER_SIZE];
size_t serialCmdIndex = 0;

//================ OUTPUT STATE =================
bool heaterState = false;
bool fanState    = false;
bool pumpState   = false;
bool mistState   = false;
bool lightState  = false;

//================ PREVIOUS OUTPUT STATE =================
bool prevHeater = false;
bool prevFan    = false;
bool prevPump   = false;
bool prevMist   = false;
bool prevLight  = false;

//================ CONTROL MODE =================
enum ControlMode
{
  MODE_AUTO = 0,
  MODE_MANUAL
};

ControlMode controlMode = MODE_AUTO;

//================ DISPLAY PAGE =================
uint8_t displayPage = 0;

//================ UI STATE =================
enum UiState
{
  UI_HOME = 0,
  UI_MAIN_MENU,
  UI_SETTINGS_MENU,
  UI_MANUAL_MENU
};

UiState uiState = UI_HOME;

//================ MAIN MENU =================
enum MainMenuItem
{
  MAIN_AUTO = 0,
  MAIN_MANUAL,
  MAIN_SETTINGS
};

MainMenuItem mainMenuIndex = MAIN_AUTO;

//================ SETTINGS MENU =================
enum SettingsMenuItem
{
  SET_TEMP_LOW = 0,
  SET_TEMP_HIGH,
  SET_AIR_HUMI_LOW,
  SET_AIR_HUMI_HIGH,
  SET_SOIL_HUMI_LOW,
  SET_SOIL_HUMI_HIGH,
  SET_SAVE_EXIT
};

SettingsMenuItem settingsMenuIndex = SET_TEMP_LOW;

//================ MANUAL MENU =================
enum ManualMenuItem
{
  MAN_HEATER = 0,
  MAN_FAN,
  MAN_PUMP,
  MAN_MIST,
  MAN_LIGHT,
  MAN_EXIT
};

ManualMenuItem manualMenuIndex = MAN_HEATER;

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

template<typename T>
T clampValue(T value, T minVal, T maxVal)
{
  if (value < minVal) return minVal;
  if (value > maxVal) return maxVal;
  return value;
}

bool validateSensorData(const SensorData& d)
{
  if (d.airTemp   < -20.0f || d.airTemp   > 80.0f)  return false;
  if (d.airHumi   <   0.0f || d.airHumi   > 100.0f) return false;
  if (d.soilTemp  < -20.0f || d.soilTemp  > 80.0f)  return false;
  if (d.soilHumi  <   0.0f || d.soilHumi  > 100.0f) return false;
  if (d.ph        <   0.0f || d.ph        > 14.0f)  return false;

  if (d.salinity  < 0) return false;
  if (d.ec        < 0) return false;
  if (d.nitrogen  < 0) return false;
  if (d.phosphorus < 0) return false;
  if (d.potassium < 0) return false;

  return true;
}

void validateSettings(Settings &s)
{
  s.tempLow      = clampValue(s.tempLow, 0.0f, 79.5f);
  s.tempHigh     = clampValue(s.tempHigh, 0.5f, 80.0f);
  s.airHumiLow   = clampValue(s.airHumiLow, 0.0f, 99.0f);
  s.airHumiHigh  = clampValue(s.airHumiHigh, 1.0f, 100.0f);
  s.soilHumiLow  = clampValue(s.soilHumiLow, 0.0f, 99.0f);
  s.soilHumiHigh = clampValue(s.soilHumiHigh, 1.0f, 100.0f);

  if (s.tempLow >= s.tempHigh)
  {
    s.tempLow = DEFAULT_CFG.tempLow;
    s.tempHigh = DEFAULT_CFG.tempHigh;
  }

  if (s.airHumiLow >= s.airHumiHigh)
  {
    s.airHumiLow = DEFAULT_CFG.airHumiLow;
    s.airHumiHigh = DEFAULT_CFG.airHumiHigh;
  }

  if (s.soilHumiLow >= s.soilHumiHigh)
  {
    s.soilHumiLow = DEFAULT_CFG.soilHumiLow;
    s.soilHumiHigh = DEFAULT_CFG.soilHumiHigh;
  }
}

//================ SERIAL SYNC =================
void sendRelayStatesToSerial()
{
  Serial.print("RELAY_STATE:");
  Serial.print("heater="); Serial.print(heaterState ? 1 : 0);
  Serial.print(",fan=");   Serial.print(fanState ? 1 : 0);
  Serial.print(",pump=");  Serial.print(pumpState ? 1 : 0);
  Serial.print(",mist=");  Serial.print(mistState ? 1 : 0);
  Serial.print(",light="); Serial.print(lightState ? 1 : 0);
  Serial.println();
}

void sendSettingsToSerial()
{
  Serial.print("CFG:");
  Serial.print("tempLow="); Serial.print(cfg.tempLow, 1);
  Serial.print(",tempHigh="); Serial.print(cfg.tempHigh, 1);
  Serial.print(",airHumiLow="); Serial.print(cfg.airHumiLow, 1);
  Serial.print(",airHumiHigh="); Serial.print(cfg.airHumiHigh, 1);
  Serial.print(",soilHumiLow="); Serial.print(cfg.soilHumiLow, 1);
  Serial.print(",soilHumiHigh="); Serial.print(cfg.soilHumiHigh, 1);
  Serial.println();
}

void sendModeToSerial()
{
  Serial.print("MODE:");
  Serial.println(controlMode == MODE_AUTO ? "AUTO" : "MANUAL");
}

//================ OUTPUT =================
void applyOutputs()
{
  relayWrite(RELAY_HEATER, heaterState);
  relayWrite(RELAY_FAN, fanState);
  relayWrite(RELAY_PUMP, pumpState);
  relayWrite(RELAY_MIST, mistState);
  relayWrite(RELAY_LIGHT, lightState);

  if (heaterState != prevHeater || fanState != prevFan ||
      pumpState != prevPump || mistState != prevMist ||
      lightState != prevLight)
  {
    sendRelayStatesToSerial();
    prevHeater = heaterState;
    prevFan = fanState;
    prevPump = pumpState;
    prevMist = mistState;
    prevLight = lightState;
  }
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

//================ SETTINGS =================
void loadSettings()
{
  prefs.begin("gateway_cfg", true);
  cfg.tempLow      = prefs.getFloat("tempLow", DEFAULT_CFG.tempLow);
  cfg.tempHigh     = prefs.getFloat("tempHigh", DEFAULT_CFG.tempHigh);
  cfg.airHumiLow   = prefs.getFloat("airLow", DEFAULT_CFG.airHumiLow);
  cfg.airHumiHigh  = prefs.getFloat("airHigh", DEFAULT_CFG.airHumiHigh);
  cfg.soilHumiLow  = prefs.getFloat("soilLow", DEFAULT_CFG.soilHumiLow);
  cfg.soilHumiHigh = prefs.getFloat("soilHigh", DEFAULT_CFG.soilHumiHigh);
  prefs.end();

  validateSettings(cfg);
}

void saveSettings()
{
  validateSettings(cfg);

  prefs.begin("gateway_cfg", false);
  prefs.putFloat("tempLow", cfg.tempLow);
  prefs.putFloat("tempHigh", cfg.tempHigh);
  prefs.putFloat("airLow", cfg.airHumiLow);
  prefs.putFloat("airHigh", cfg.airHumiHigh);
  prefs.putFloat("soilLow", cfg.soilHumiLow);
  prefs.putFloat("soilHigh", cfg.soilHumiHigh);
  prefs.end();

  sendSettingsToSerial();
}

//================ PARSE DATA =================
bool parseDataPacket(const char* packet, SensorData& outData)
{
  if (packet == nullptr) return false;

  size_t len = strlen(packet);
  if (len < 3) return false;
  if (packet[0] != '<' || packet[len - 1] != '>') return false;

  size_t copyLen = len - 2;
  if (copyLen >= LORA_BUFFER_SIZE) return false;

  char temp[LORA_BUFFER_SIZE];
  strncpy(temp, packet + 1, copyLen);
  temp[copyLen] = '\0';

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

  return validateSensorData(outData);
}

//================ SERIAL COMMANDS =================
void parseCfgFromSerial(const char* cfgStr)
{
  Settings newCfg = cfg;

  char buf[SERIAL_CMD_BUFFER_SIZE];
  strncpy(buf, cfgStr, sizeof(buf) - 1);
  buf[sizeof(buf) - 1] = '\0';

  char* savePtr = nullptr;
  char* pair = strtok_r(buf, ",", &savePtr);

  while (pair != nullptr)
  {
    char* eq = strchr(pair, '=');
    if (eq != nullptr)
    {
      *eq = '\0';
      char* key = pair;
      float val = atof(eq + 1);

      if (strcmp(key, "tempLow") == 0)            newCfg.tempLow = val;
      else if (strcmp(key, "tempHigh") == 0)      newCfg.tempHigh = val;
      else if (strcmp(key, "airHumiLow") == 0)    newCfg.airHumiLow = val;
      else if (strcmp(key, "airHumiHigh") == 0)   newCfg.airHumiHigh = val;
      else if (strcmp(key, "soilHumiLow") == 0)   newCfg.soilHumiLow = val;
      else if (strcmp(key, "soilHumiHigh") == 0)  newCfg.soilHumiHigh = val;
    }
    pair = strtok_r(nullptr, ",", &savePtr);
  }

  validateSettings(newCfg);
  cfg = newCfg;
  saveSettings();

  Serial.println(">> CFG updated from web!");
}

void handleRelayCommand(const char* relayCmd)
{
  char cmdCopy[64];
  strncpy(cmdCopy, relayCmd, sizeof(cmdCopy) - 1);
  cmdCopy[sizeof(cmdCopy) - 1] = '\0';

  char* colon = strchr(cmdCopy, ':');
  if (colon == nullptr) return;

  *colon = '\0';
  char* relayName = cmdCopy;
  char* stateStr = colon + 1;

  bool validState = false;
  bool state = false;

  if (strcmp(stateStr, "ON") == 0)
  {
    validState = true;
    state = true;
  }
  else if (strcmp(stateStr, "OFF") == 0)
  {
    validState = true;
    state = false;
  }

  if (!validState) return;

  // CHI CHO DIEU KHIEN TAY KHI DANG MANUAL
  if (controlMode != MODE_MANUAL)
  {
    Serial.println(">> IGNORE: relay command only works in MANUAL mode");
    return;
  }

  if (strcmp(relayName, "HEATER") == 0)         { heaterState = state; }
  else if (strcmp(relayName, "FAN") == 0)       { fanState = state; }
  else if (strcmp(relayName, "PUMP") == 0)      { pumpState = state; }
  else if (strcmp(relayName, "MIST") == 0)      { mistState = state; }
  else if (strcmp(relayName, "LIGHT") == 0)     { lightState = state; }
  else { return; }

  applyOutputs();

  Serial.print(">> OK: ");
  Serial.print(relayName);
  Serial.print(" = ");
  Serial.println(state ? "ON" : "OFF");
}

void handleModeCommand(const char* modeCmd)
{
  if (strcmp(modeCmd, "AUTO") == 0)
  {
    controlMode = MODE_AUTO;

    if (hasValidData)
      controlOutputsAuto(currentData);
    else
      turnOffAllOutputs();

    sendModeToSerial();
    Serial.println(">> MODE set to AUTO");

    if (uiState == UI_HOME) updateHomeDisplay();
    else if (uiState == UI_MAIN_MENU) displayMainMenu();
    else if (uiState == UI_SETTINGS_MENU) displaySettingsMenu();
    else if (uiState == UI_MANUAL_MENU) displayManualMenu();
  }
  else if (strcmp(modeCmd, "MANUAL") == 0)
  {
    controlMode = MODE_MANUAL;
    sendModeToSerial();
    Serial.println(">> MODE set to MANUAL");

    if (uiState == UI_HOME) updateHomeDisplay();
    else if (uiState == UI_MAIN_MENU) displayMainMenu();
    else if (uiState == UI_SETTINGS_MENU) displaySettingsMenu();
    else if (uiState == UI_MANUAL_MENU) displayManualMenu();
  }
}

void handleSerialCommand(const char* cmd)
{
  if (strncmp(cmd, "CFG:", 4) == 0)
  {
    parseCfgFromSerial(cmd + 4);
  }
  else if (strncmp(cmd, "RELAY:", 6) == 0)
  {
    handleRelayCommand(cmd + 6);
  }
  else if (strncmp(cmd, "MODE:", 5) == 0)
  {
    handleModeCommand(cmd + 5);
  }
  else if (strcmp(cmd, "GET:MODE") == 0)
  {
    sendModeToSerial();
  }
  else if (strcmp(cmd, "GET:CFG") == 0)
  {
    sendSettingsToSerial();
  }
  else if (strcmp(cmd, "GET:RELAY") == 0)
  {
    sendRelayStatesToSerial();
  }
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
        serialCmdIndex = 0;
      }
    }
  }
}

//================ LCD =================
void printModeCorner()
{
  lcd.setCursor(16, 3);
  if (controlMode == MODE_AUTO) lcd.print("AUTO");
  else lcd.print(" MAN");
}

void displayPage1(const SensorData& d)
{
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Ta:"); lcd.print(d.airTemp, 1);
  lcd.print("C  Ha:"); lcd.print(d.airHumi, 0); lcd.print("%");

  lcd.setCursor(0, 1);
  lcd.print("Ts:"); lcd.print(d.soilTemp, 1);
  lcd.print("C  Hs:"); lcd.print(d.soilHumi, 0); lcd.print("%");

  lcd.setCursor(0, 2);
  lcd.print("EC:"); lcd.print(d.ec);

  lcd.setCursor(0, 3);
  lcd.print("Sal:"); lcd.print(d.salinity);

  lcd.setCursor(17, 0); lcd.print("[1]");
  printModeCorner();
}

void displayPage2(const SensorData& d)
{
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("N:"); lcd.print(d.nitrogen);
  lcd.setCursor(0, 1); lcd.print("P:"); lcd.print(d.phosphorus);
  lcd.setCursor(0, 2); lcd.print("K:"); lcd.print(d.potassium);
  lcd.setCursor(0, 3); lcd.print("pH:"); lcd.print(d.ph, 1);
  lcd.setCursor(17, 0); lcd.print("[2]");
  printModeCorner();
}

void updateHomeDisplay()
{
  if (!hasValidData)
  {
    lcd.clear();
    lcd.setCursor(0, 0); lcd.print("Waiting data...");
    lcd.setCursor(0, 1); lcd.print("Press MODE menu");
    lcd.setCursor(17, 0);
    lcd.print(displayPage == 0 ? "[1]" : "[2]");
    printModeCorner();
    return;
  }

  if (displayPage == 0) displayPage1(currentData);
  else displayPage2(currentData);
}

void displayNodeDisconnected()
{
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("Node disconnected");
  lcd.setCursor(0, 1); lcd.print("No recent data");
  lcd.setCursor(0, 2); lcd.print("All outputs OFF");
  lcd.setCursor(0, 3); lcd.print("Press MODE");
  printModeCorner();
}

void displayMainMenu()
{
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("=== MAIN MENU ===");
  lcd.setCursor(0, 1);
  lcd.print(mainMenuIndex == MAIN_AUTO ? ">" : " "); lcd.print("AUTO MODE");
  lcd.setCursor(0, 2);
  lcd.print(mainMenuIndex == MAIN_MANUAL ? ">" : " "); lcd.print("MANUAL MODE");
  lcd.setCursor(0, 3);
  lcd.print(mainMenuIndex == MAIN_SETTINGS ? ">" : " "); lcd.print("SETTINGS");
}

void displaySettingsMenu()
{
  lcd.clear();
  switch (settingsMenuIndex)
  {
    case SET_TEMP_LOW:
      lcd.setCursor(0, 0); lcd.print("TEMP LOW");
      lcd.setCursor(0, 1); lcd.print("Below -> HEATER ON");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.tempLow, 1); lcd.print(" C");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_TEMP_HIGH:
      lcd.setCursor(0, 0); lcd.print("TEMP HIGH");
      lcd.setCursor(0, 1); lcd.print("Above -> FAN ON");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.tempHigh, 1); lcd.print(" C");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_AIR_HUMI_LOW:
      lcd.setCursor(0, 0); lcd.print("AIR HUMI LOW");
      lcd.setCursor(0, 1); lcd.print("Below -> MIST ON");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.airHumiLow, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_AIR_HUMI_HIGH:
      lcd.setCursor(0, 0); lcd.print("AIR HUMI HIGH");
      lcd.setCursor(0, 1); lcd.print("Above -> MIST OFF");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.airHumiHigh, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_SOIL_HUMI_LOW:
      lcd.setCursor(0, 0); lcd.print("SOIL HUMI LOW");
      lcd.setCursor(0, 1); lcd.print("Below -> PUMP ON");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.soilHumiLow, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_SOIL_HUMI_HIGH:
      lcd.setCursor(0, 0); lcd.print("SOIL HUMI HIGH");
      lcd.setCursor(0, 1); lcd.print("Above -> PUMP OFF");
      lcd.setCursor(0, 2); lcd.print("Value: "); lcd.print(cfg.soilHumiHigh, 1); lcd.print(" %");
      lcd.setCursor(0, 3); lcd.print("UP/DN edit MODE>");
      break;
    case SET_SAVE_EXIT:
      lcd.setCursor(0, 0); lcd.print("SAVE & EXIT ?");
      lcd.setCursor(0, 1); lcd.print("UP = Save");
      lcd.setCursor(0, 2); lcd.print("DOWN = Exit");
      lcd.setCursor(0, 3); lcd.print("MODE = Next");
      break;
  }
}

void displayManualMenu()
{
  lcd.clear();
  switch (manualMenuIndex)
  {
    case MAN_HEATER:
      lcd.setCursor(0, 0); lcd.print("MANUAL: HEATER");
      lcd.setCursor(0, 1); lcd.print("State: "); lcd.print(heaterState ? "ON" : "OFF");
      lcd.setCursor(0, 2); lcd.print("UP=ON  DOWN=OFF");
      lcd.setCursor(0, 3); lcd.print("MODE=Next");
      break;

    case MAN_FAN:
      lcd.setCursor(0, 0); lcd.print("MANUAL: FAN");
      lcd.setCursor(0, 1); lcd.print("State: "); lcd.print(fanState ? "ON" : "OFF");
      lcd.setCursor(0, 2); lcd.print("UP=ON  DOWN=OFF");
      lcd.setCursor(0, 3); lcd.print("MODE=Next");
      break;

    case MAN_PUMP:
      lcd.setCursor(0, 0); lcd.print("MANUAL: PUMP");
      lcd.setCursor(0, 1); lcd.print("State: "); lcd.print(pumpState ? "ON" : "OFF");
      lcd.setCursor(0, 2); lcd.print("UP=ON  DOWN=OFF");
      lcd.setCursor(0, 3); lcd.print("MODE=Next");
      break;

    case MAN_MIST:
      lcd.setCursor(0, 0); lcd.print("MANUAL: MIST");
      lcd.setCursor(0, 1); lcd.print("State: "); lcd.print(mistState ? "ON" : "OFF");
      lcd.setCursor(0, 2); lcd.print("UP=ON  DOWN=OFF");
      lcd.setCursor(0, 3); lcd.print("MODE=Next");
      break;

    case MAN_LIGHT:
      lcd.setCursor(0, 0); lcd.print("MANUAL: LIGHT");
      lcd.setCursor(0, 1); lcd.print("State: "); lcd.print(lightState ? "ON" : "OFF");
      lcd.setCursor(0, 2); lcd.print("UP=ON  DOWN=OFF");
      lcd.setCursor(0, 3); lcd.print("MODE=Next");
      break;

    case MAN_EXIT:
      lcd.setCursor(0, 0); lcd.print("EXIT MANUAL ?");
      lcd.setCursor(0, 1); lcd.print("UP = Home");
      lcd.setCursor(0, 2); lcd.print("DOWN = Stay");
      lcd.setCursor(0, 3); lcd.print("MODE = Next");
      break;
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
bool upPressed()   { return readButtonEdge(BTN_UP, lastUpReading, lastUpMs); }
bool downPressed() { return readButtonEdge(BTN_DOWN, lastDownReading, lastDownMs); }

//================ AUTO CONTROL =================
void controlOutputsAuto(const SensorData& data)
{
  if (controlMode != MODE_AUTO) return;

  if (data.airTemp < cfg.tempLow)
  {
    heaterState = true;
    fanState = false;
  }
  else if (data.airTemp > cfg.tempHigh)
  {
    heaterState = false;
    fanState = true;
  }
  else
  {
    heaterState = false;
    fanState = false;
  }

  if (data.airHumi < cfg.airHumiLow)       mistState = true;
  else if (data.airHumi > cfg.airHumiHigh) mistState = false;

  if (data.soilHumi < cfg.soilHumiLow)       pumpState = true;
  else if (data.soilHumi > cfg.soilHumiHigh) pumpState = false;

  // LIGHT KHONG THAM GIA AUTO
  applyOutputs();
}

//================ UI =================
void enterHome()
{
  uiState = UI_HOME;
  updateHomeDisplay();
}

void enterMainMenu()
{
  uiState = UI_MAIN_MENU;
  mainMenuIndex = MAIN_AUTO;
  displayMainMenu();
}

void enterSettingsMenu()
{
  uiState = UI_SETTINGS_MENU;
  settingsMenuIndex = SET_TEMP_LOW;
  displaySettingsMenu();
}

void enterManualMenu()
{
  uiState = UI_MANUAL_MENU;
  manualMenuIndex = MAN_HEATER;
  controlMode = MODE_MANUAL;
  sendModeToSerial();
  displayManualMenu();
}

void handleHomeButtons()
{
  if (modePressed()) { enterMainMenu(); return; }
  if (upPressed())   { displayPage = (displayPage + 1) % 2; updateHomeDisplay(); }
  if (downPressed()) { displayPage = (displayPage == 0) ? 1 : 0; updateHomeDisplay(); }
}

void handleMainMenuButtons()
{
  if (upPressed())
  {
    if (mainMenuIndex == MAIN_AUTO) mainMenuIndex = MAIN_SETTINGS;
    else mainMenuIndex = (MainMenuItem)((int)mainMenuIndex - 1);
    displayMainMenu();
  }

  if (downPressed())
  {
    if (mainMenuIndex == MAIN_SETTINGS) mainMenuIndex = MAIN_AUTO;
    else mainMenuIndex = (MainMenuItem)((int)mainMenuIndex + 1);
    displayMainMenu();
  }

  if (modePressed())
  {
    if (mainMenuIndex == MAIN_AUTO)
    {
      controlMode = MODE_AUTO;
      sendModeToSerial();

      if (hasValidData) controlOutputsAuto(currentData);
      else turnOffAllOutputs();

      enterHome();
    }
    else if (mainMenuIndex == MAIN_MANUAL)
    {
      enterManualMenu();
    }
    else if (mainMenuIndex == MAIN_SETTINGS)
    {
      enterSettingsMenu();
    }
  }
}

void increaseSetting()
{
  switch (settingsMenuIndex)
  {
    case SET_TEMP_LOW:
      cfg.tempLow += 0.5;
      if (cfg.tempLow >= cfg.tempHigh) cfg.tempLow = cfg.tempHigh - 0.5;
      break;
    case SET_TEMP_HIGH:
      cfg.tempHigh += 0.5;
      if (cfg.tempHigh <= cfg.tempLow) cfg.tempHigh = cfg.tempLow + 0.5;
      break;
    case SET_AIR_HUMI_LOW:
      cfg.airHumiLow += 1.0;
      if (cfg.airHumiLow >= cfg.airHumiHigh) cfg.airHumiLow = cfg.airHumiHigh - 1.0;
      break;
    case SET_AIR_HUMI_HIGH:
      cfg.airHumiHigh += 1.0;
      if (cfg.airHumiHigh <= cfg.airHumiLow) cfg.airHumiHigh = cfg.airHumiLow + 1.0;
      break;
    case SET_SOIL_HUMI_LOW:
      cfg.soilHumiLow += 1.0;
      if (cfg.soilHumiLow >= cfg.soilHumiHigh) cfg.soilHumiLow = cfg.soilHumiHigh - 1.0;
      break;
    case SET_SOIL_HUMI_HIGH:
      cfg.soilHumiHigh += 1.0;
      if (cfg.soilHumiHigh <= cfg.soilHumiLow) cfg.soilHumiHigh = cfg.soilHumiLow + 1.0;
      break;
    case SET_SAVE_EXIT:
      saveSettings();
      if (controlMode == MODE_AUTO && hasValidData) controlOutputsAuto(currentData);
      enterHome();
      return;
  }

  validateSettings(cfg);
  displaySettingsMenu();
}

void decreaseSetting()
{
  switch (settingsMenuIndex)
  {
    case SET_TEMP_LOW:
      cfg.tempLow -= 0.5;
      if (cfg.tempLow >= cfg.tempHigh) cfg.tempLow = cfg.tempHigh - 0.5;
      break;
    case SET_TEMP_HIGH:
      cfg.tempHigh -= 0.5;
      if (cfg.tempHigh <= cfg.tempLow) cfg.tempHigh = cfg.tempLow + 0.5;
      break;
    case SET_AIR_HUMI_LOW:
      cfg.airHumiLow -= 1.0;
      break;
    case SET_AIR_HUMI_HIGH:
      cfg.airHumiHigh -= 1.0;
      if (cfg.airHumiHigh <= cfg.airHumiLow) cfg.airHumiHigh = cfg.airHumiLow + 1.0;
      break;
    case SET_SOIL_HUMI_LOW:
      cfg.soilHumiLow -= 1.0;
      break;
    case SET_SOIL_HUMI_HIGH:
      cfg.soilHumiHigh -= 1.0;
      if (cfg.soilHumiHigh <= cfg.soilHumiLow) cfg.soilHumiHigh = cfg.soilHumiLow + 1.0;
      break;
    case SET_SAVE_EXIT:
      enterHome();
      return;
  }

  validateSettings(cfg);
  displaySettingsMenu();
}

void handleSettingsButtons()
{
  if (modePressed())
  {
    if (settingsMenuIndex == SET_SAVE_EXIT) settingsMenuIndex = SET_TEMP_LOW;
    else settingsMenuIndex = (SettingsMenuItem)((int)settingsMenuIndex + 1);
    displaySettingsMenu();
  }
  if (upPressed()) increaseSetting();
  if (downPressed()) decreaseSetting();
}

void handleManualButtons()
{
  if (modePressed())
  {
    if (manualMenuIndex == MAN_EXIT) manualMenuIndex = MAN_HEATER;
    else manualMenuIndex = (ManualMenuItem)((int)manualMenuIndex + 1);
    displayManualMenu();
  }

  if (upPressed())
  {
    switch (manualMenuIndex)
    {
      case MAN_HEATER: heaterState = true;  applyOutputs(); break;
      case MAN_FAN:    fanState    = true;  applyOutputs(); break;
      case MAN_PUMP:   pumpState   = true;  applyOutputs(); break;
      case MAN_MIST:   mistState   = true;  applyOutputs(); break;
      case MAN_LIGHT:  lightState  = true;  applyOutputs(); break;
      case MAN_EXIT:   enterHome(); return;
    }
    displayManualMenu();
  }

  if (downPressed())
  {
    switch (manualMenuIndex)
    {
      case MAN_HEATER: heaterState = false; applyOutputs(); break;
      case MAN_FAN:    fanState    = false; applyOutputs(); break;
      case MAN_PUMP:   pumpState   = false; applyOutputs(); break;
      case MAN_MIST:   mistState   = false; applyOutputs(); break;
      case MAN_LIGHT:  lightState  = false; applyOutputs(); break;
      case MAN_EXIT:   displayManualMenu(); return;
    }
    displayManualMenu();
  }
}

void handleButtons()
{
  switch (uiState)
  {
    case UI_HOME:          handleHomeButtons(); break;
    case UI_MAIN_MENU:     handleMainMenuButtons(); break;
    case UI_SETTINGS_MENU: handleSettingsButtons(); break;
    case UI_MANUAL_MENU:   handleManualButtons(); break;
  }
}

//================ NODE TIMEOUT =================
void checkNodeTimeout()
{
  if (hasValidData && (millis() - lastNodeTime > NODE_TIMEOUT_MS))
  {
    hasValidData = false;
    turnOffAllOutputs();
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

      if (controlMode == MODE_AUTO)
      {
        controlOutputsAuto(currentData);
      }

      if (uiState == UI_HOME)
      {
        updateHomeDisplay();
      }
    }
    else
    {
      Serial.println(">> Invalid sensor packet");
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
  delay(500);
  Serial.println("=== GATEWAY BOOT ===");

  setupPins();
  loadSettings();

  Wire.begin(I2C_SDA, I2C_SCL);
  lcd.init();
  lcd.backlight();

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("NHA KINH THONG MINH");
  lcd.setCursor(0, 1); lcd.print("DH SPKT HUNG YEN");


  LORA.begin(LORA_BAUD, SERIAL_8N1, LORA_RX, LORA_TX, false, 256);
  resetLoRaBuffer();
  memset(serialCmdBuffer, 0, sizeof(serialCmdBuffer));

  delay(5000);

  sendSettingsToSerial();
  sendRelayStatesToSerial();
  sendModeToSerial();
  Serial.println("=== READY ===");

  enterHome();
}

void loop()
{
  handleButtons();
  readSerialCommands();

  if (LORA.available() > 0)
  {
    char c = (char)LORA.read();
    handleLoRaChar(c);
  }

  checkNodeTimeout();
}
