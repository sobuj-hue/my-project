# Green AI — Smart Gate Lock

A complete ESP32-based smart gate lock for home automation.

## Features

- RFID card access (tap to unlock)
- PIN keypad (4–6 digit code)
- WiFi remote control (open/close from phone browser)
- LCD display with real-time feedback
- Auto-lock after 5 seconds
- Wrong attempt lockout (5 attempts → 30s lockout)
- Alarm buzzer on security breach
- PIN saved in EEPROM (survives power cuts)
- Change PIN remotely via WiFi

## Hardware Required

| Component | Notes |
|---|---|
| ESP32 Dev Board | Any 30-pin variant |
| MFRC522 RFID Reader | With 2x cards |
| 4×4 Membrane Keypad | |
| 16×2 LCD + I2C module | I2C address 0x27 or 0x3F |
| 12V Solenoid Door Lock | |
| 5V Relay Module | 1-channel |
| Active Buzzer | 5V |
| 12V 2A Power Supply | |

All available at Elephant Road or Agargaon, Dhaka (~৳1,500–2,200 total)

## Wiring

```
ESP32 Pin    Component
─────────────────────────────────────
GPIO 5   →   RFID SDA (SS)
GPIO 18  →   RFID SCK
GPIO 23  →   RFID MOSI
GPIO 19  →   RFID MISO
GPIO 4   →   RFID RST
GPIO 13  →   Keypad Row 1
GPIO 12  →   Keypad Row 2
GPIO 14  →   Keypad Row 3
GPIO 27  →   Keypad Row 4
GPIO 26  →   Keypad Col 1
GPIO 25  →   Keypad Col 2
GPIO 33  →   Keypad Col 3
GPIO 32  →   Keypad Col 4
GPIO 21  →   LCD SDA
GPIO 22  →   LCD SCL
GPIO 2   →   Relay IN
GPIO 15  →   Buzzer +
3.3V     →   RFID VCC
5V       →   LCD, Relay, Buzzer VCC
GND      →   All GND
```

## Setup Steps

1. Install Arduino IDE + ESP32 board support
2. Install libraries: MFRC522, Keypad, LiquidCrystal_I2C
3. Upload `CardScanner.ino` first → scan cards → copy UIDs
4. Edit `SmartGateLock.ino`:
   - Set your WiFi name and password
   - Paste your card UIDs into `authorizedCards[]`
   - Set your desired PIN
5. Upload `SmartGateLock.ino`
6. LCD shows IP address — open it in phone browser on same WiFi

## Daily Usage

| Action | How |
|---|---|
| Unlock with card | Tap RFID card on reader |
| Unlock with PIN | Type PIN → press `#` |
| Unlock from phone | Open IP in browser → tap Open |
| Lock manually | Press `D` on keypad |
| Clear PIN entry | Press `*` |
| Change PIN | Via phone browser web panel |
