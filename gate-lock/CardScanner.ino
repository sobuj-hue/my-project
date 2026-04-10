/*
 * ═══════════════════════════════════════════════════
 *  RFID Card UID Scanner
 *  Run this FIRST to find your card UIDs,
 *  then copy them into SmartGateLock.ino
 * ═══════════════════════════════════════════════════
 */

#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN  5
#define RST_PIN 4

MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("==============================");
  Serial.println(" RFID Card UID Scanner Ready");
  Serial.println(" Scan a card to see its UID");
  Serial.println("==============================");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  Serial.println("Card UID: " + uid);
  Serial.println("Copy this into authorizedCards[] in SmartGateLock.ino");
  Serial.println("------------------------------");

  rfid.PICC_HaltA();
  delay(1000);
}
