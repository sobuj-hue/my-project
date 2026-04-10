/*
 * ═══════════════════════════════════════════════════
 *  Green AI Smart Gate Lock — ESP32
 *  Features: RFID | PIN Keypad | WiFi Web Control
 * ═══════════════════════════════════════════════════
 *
 * Libraries needed (install via Arduino Library Manager):
 *   - MFRC522       by GithubCommunity
 *   - Keypad        by Mark Stanley
 *   - LiquidCrystal_I2C  by Frank de Brabander
 *   - WiFi          (built-in with ESP32)
 */

#include <SPI.h>
#include <MFRC522.h>
#include <Keypad.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <WebServer.h>
#include <EEPROM.h>

// ─── WiFi Credentials (change these) ───────────────
const char* WIFI_SSID     = "YourWiFiName";
const char* WIFI_PASSWORD = "YourWiFiPassword";

// ─── PIN Configuration ──────────────────────────────
String MASTER_PIN = "1234";          // Change this!
const int MAX_PIN_LENGTH = 6;
const int MAX_WRONG_ATTEMPTS = 5;    // Lockout after 5 wrong tries
const int LOCKOUT_DURATION = 30000;  // 30 seconds lockout

// ─── RFID Authorized Card UIDs ──────────────────────
// Add your RFID card UIDs here (read them using the scanner below)
String authorizedCards[] = {
  "A3F2C1D4",   // Card 1 — Main family card
  "B1E4D2C3",   // Card 2 — Spare card
};
const int NUM_CARDS = 2;

// ─── Pin Definitions ────────────────────────────────
#define RFID_SS_PIN   5
#define RFID_RST_PIN  4
#define RELAY_PIN     2
#define BUZZER_PIN    15
#define LOCK_OPEN_TIME 5000  // Lock stays open 5 seconds

// ─── Keypad Layout ──────────────────────────────────
const byte ROWS = 4, COLS = 4;
char keys[ROWS][COLS] = {
  {'1','2','3','A'},
  {'4','5','6','B'},
  {'7','8','9','C'},
  {'*','0','#','D'}
};
byte rowPins[ROWS] = {13, 12, 14, 27};
byte colPins[COLS] = {26, 25, 33, 32};

// ─── Objects ─────────────────────────────────────────
MFRC522 rfid(RFID_SS_PIN, RFID_RST_PIN);
Keypad keypad = Keypad(makeKeymap(keys), rowPins, colPins, ROWS, COLS);
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Try 0x3F if 0x27 doesn't work
WebServer server(80);

// ─── State Variables ─────────────────────────────────
String enteredPIN = "";
bool lockOpen = false;
unsigned long lockOpenTime = 0;
int wrongAttempts = 0;
bool isLockedOut = false;
unsigned long lockoutStart = 0;
bool wifiConnected = false;

// ═══════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  EEPROM.begin(64);

  // Pins
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH);  // HIGH = locked (relay NC)

  // LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  showMessage("Green AI Lock", "Initializing...");

  // RFID
  SPI.begin();
  rfid.PCD_Init();

  // Load saved PIN from EEPROM (if any)
  loadPINFromEEPROM();

  // WiFi
  connectWiFi();

  // Web server routes
  server.on("/",       handleRoot);
  server.on("/open",   handleOpen);
  server.on("/close",  handleClose);
  server.on("/status", handleStatus);
  server.on("/setpin", handleSetPIN);
  server.begin();

  showMessage("System Ready", wifiConnected ? WiFi.localIP().toString() : "No WiFi");
  delay(2000);
  showStandby();
}

// ═══════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════
void loop() {
  if (wifiConnected) server.handleClient();

  if (lockOpen && millis() - lockOpenTime >= LOCK_OPEN_TIME) {
    closeLock();
  }

  if (isLockedOut && millis() - lockoutStart >= LOCKOUT_DURATION) {
    isLockedOut = false;
    wrongAttempts = 0;
    showMessage("Lockout Cleared", "Try again");
    delay(1500);
    showStandby();
  }

  if (isLockedOut) return;

  checkRFID();
  checkKeypad();
}

// ═══════════════════════════════════════════════════
// RFID CHECK
// ═══════════════════════════════════════════════════
void checkRFID() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

  String cardUID = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) cardUID += "0";
    cardUID += String(rfid.uid.uidByte[i], HEX);
  }
  cardUID.toUpperCase();

  Serial.println("Card detected: " + cardUID);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Card: " + cardUID);

  if (isCardAuthorized(cardUID)) {
    grantAccess("RFID Card");
  } else {
    denyAccess("Unknown Card");
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

bool isCardAuthorized(String uid) {
  for (int i = 0; i < NUM_CARDS; i++) {
    if (uid == authorizedCards[i]) return true;
  }
  return false;
}

// ═══════════════════════════════════════════════════
// KEYPAD CHECK
// ═══════════════════════════════════════════════════
void checkKeypad() {
  char key = keypad.getKey();
  if (!key) return;

  beep(50);

  if (key == '#') {
    if (enteredPIN == MASTER_PIN) {
      grantAccess("PIN Code");
    } else {
      denyAccess("Wrong PIN");
    }
    enteredPIN = "";
    return;
  }

  if (key == '*') {
    enteredPIN = "";
    showStandby();
    return;
  }

  if (key == 'A') {
    showMessage("Scan RFID Card", "or enter PIN");
    return;
  }

  if (key == 'D') {
    closeLock();
    return;
  }

  if (enteredPIN.length() < MAX_PIN_LENGTH) {
    enteredPIN += key;
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Enter PIN:");
    lcd.setCursor(0, 1);
    String masked = "";
    for (int i = 0; i < enteredPIN.length(); i++) masked += "*";
    lcd.print(masked);
  }
}

// ═══════════════════════════════════════════════════
// ACCESS CONTROL
// ═══════════════════════════════════════════════════
void grantAccess(String method) {
  Serial.println("ACCESS GRANTED via " + method);
  showMessage("ACCESS GRANTED", method);
  openLock();
  wrongAttempts = 0;
  successBeep();
}

void denyAccess(String reason) {
  wrongAttempts++;
  Serial.println("ACCESS DENIED: " + reason + " (attempt " + wrongAttempts + ")");

  if (wrongAttempts >= MAX_WRONG_ATTEMPTS) {
    isLockedOut = true;
    lockoutStart = millis();
    showMessage("!! LOCKED OUT !!", "Wait 30 seconds");
    alarmBeep();
    return;
  }

  showMessage("ACCESS DENIED", reason + " (" + (MAX_WRONG_ATTEMPTS - wrongAttempts) + " left)");
  errorBeep();
  delay(2000);
  showStandby();
}

// ═══════════════════════════════════════════════════
// LOCK CONTROL
// ═══════════════════════════════════════════════════
void openLock() {
  digitalWrite(RELAY_PIN, LOW);
  lockOpen = true;
  lockOpenTime = millis();
  Serial.println("Lock OPENED");
}

void closeLock() {
  digitalWrite(RELAY_PIN, HIGH);
  lockOpen = false;
  Serial.println("Lock CLOSED");
  showMessage("Gate Locked", "Scan or Enter PIN");
  delay(1500);
  showStandby();
}

// ═══════════════════════════════════════════════════
// WEB SERVER
// ═══════════════════════════════════════════════════
void handleRoot() {
  String html = R"rawHTML(
<!DOCTYPE html>
<html>
<head>
  <meta charset='UTF-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Green AI Gate Lock</title>
  <style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{font-family:sans-serif;background:#09090b;color:#f4f4f5;
         display:flex;flex-direction:column;align-items:center;padding:24px;min-height:100vh}
    h1{font-size:22px;margin-bottom:4px}
    .sub{color:#71717a;font-size:13px;margin-bottom:32px}
    .status{padding:14px 28px;border-radius:12px;font-weight:700;font-size:18px;
            margin-bottom:28px;text-align:center;min-width:200px}
    .locked{background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);color:#f87171}
    .open{background:rgba(74,222,128,.15);border:1px solid rgba(74,222,128,.3);color:#4ade80}
    .btn{display:block;width:220px;padding:16px;border-radius:12px;border:none;
         font-size:16px;font-weight:700;cursor:pointer;margin:10px;text-align:center;
         text-decoration:none;transition:opacity .2s}
    .btn-open{background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff}
    .btn-close{background:#1c1c1e;border:1px solid rgba(255,255,255,.1);color:#f4f4f5}
    .btn:hover{opacity:.85}
    .pin-form{margin-top:24px;display:flex;flex-direction:column;align-items:center;gap:10px}
    .pin-form input{background:#1c1c1e;border:1px solid rgba(255,255,255,.1);color:#f4f4f5;
                    padding:12px 16px;border-radius:10px;font-size:16px;width:220px;text-align:center}
    .pin-form label{font-size:13px;color:#71717a}
    .info{margin-top:24px;font-size:12px;color:#3f3f46;text-align:center}
  </style>
</head>
<body>
  <h1>Green AI Gate Lock</h1>
  <p class='sub'>Remote Access Control</p>
)rawHTML";

  html += lockOpen
    ? "  <div class='status open'>&#128275; GATE OPEN</div>\n"
    : "  <div class='status locked'>&#128274; GATE LOCKED</div>\n";

  html += R"rawHTML(
  <a href='/open'  class='btn btn-open'>&#128275; Open Gate</a>
  <a href='/close' class='btn btn-close'>&#128274; Close Gate</a>
  <div class='pin-form'>
    <label>Change PIN via WiFi</label>
    <form action='/setpin' method='GET'>
      <input type='password' name='pin' placeholder='New PIN (4-6 digits)' maxlength='6'>
      <br><br>
      <input type='submit' class='btn btn-open' value='Update PIN' style='border:none;cursor:pointer'>
    </form>
  </div>
  <p class='info'>Lock auto-closes 5 seconds after opening</p>
</body>
</html>)rawHTML";

  server.send(200, "text/html", html);
}

void handleOpen() {
  openLock();
  showMessage("WiFi Remote", "Gate Opened");
  successBeep();
  server.sendHeader("Location", "/");
  server.send(302);
}

void handleClose() {
  closeLock();
  server.sendHeader("Location", "/");
  server.send(302);
}

void handleStatus() {
  String json = "{\"locked\":" + String(lockOpen ? "false" : "true") +
                ",\"ip\":\"" + WiFi.localIP().toString() + "\"}";
  server.send(200, "application/json", json);
}

void handleSetPIN() {
  if (server.hasArg("pin")) {
    String newPIN = server.arg("pin");
    if (newPIN.length() >= 4 && newPIN.length() <= 6) {
      MASTER_PIN = newPIN;
      savePINToEEPROM(newPIN);
      showMessage("PIN Updated!", "Via WiFi");
      successBeep();
    }
  }
  server.sendHeader("Location", "/");
  server.send(302);
}

// ═══════════════════════════════════════════════════
// WIFI
// ═══════════════════════════════════════════════════
void connectWiFi() {
  showMessage("Connecting WiFi", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500);
    tries++;
  }
  wifiConnected = (WiFi.status() == WL_CONNECTED);
  if (wifiConnected) {
    Serial.println("WiFi connected: " + WiFi.localIP().toString());
  } else {
    Serial.println("WiFi failed — offline mode active");
  }
}

// ═══════════════════════════════════════════════════
// EEPROM — saves PIN across power cuts
// ═══════════════════════════════════════════════════
void savePINToEEPROM(String pin) {
  EEPROM.write(0, pin.length());
  for (int i = 0; i < pin.length(); i++) EEPROM.write(i + 1, pin[i]);
  EEPROM.commit();
}

void loadPINFromEEPROM() {
  int len = EEPROM.read(0);
  if (len >= 4 && len <= 6) {
    String pin = "";
    for (int i = 0; i < len; i++) pin += char(EEPROM.read(i + 1));
    if (pin.toInt() > 0) MASTER_PIN = pin;
  }
}

// ═══════════════════════════════════════════════════
// DISPLAY HELPERS
// ═══════════════════════════════════════════════════
void showMessage(String line1, String line2) {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print(line1.substring(0, 16));
  lcd.setCursor(0, 1); lcd.print(line2.substring(0, 16));
}

void showStandby() {
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("Scan Card or");
  lcd.setCursor(0, 1); lcd.print("Enter PIN + #");
}

// ═══════════════════════════════════════════════════
// BUZZER SOUNDS
// ═══════════════════════════════════════════════════
void beep(int ms) {
  digitalWrite(BUZZER_PIN, HIGH); delay(ms); digitalWrite(BUZZER_PIN, LOW);
}

void successBeep() {
  beep(100); delay(80); beep(100); delay(80); beep(200);
}

void errorBeep() {
  beep(400); delay(100); beep(400);
}

void alarmBeep() {
  for (int i = 0; i < 10; i++) { beep(200); delay(100); }
}
