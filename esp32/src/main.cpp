#include <Arduino.h>

namespace {
constexpr int kTriggerPin = 4;
constexpr int kPiRxPin = 18;
constexpr int kPiTxPin = 17;
constexpr uint32_t kBaudRate = 115200;

void emitTriggerPulse(uint32_t durationMs) {
  digitalWrite(kTriggerPin, HIGH);
  delay(durationMs);
  digitalWrite(kTriggerPin, LOW);
}

void handleCommand(String command) {
  command.trim();
  command.toUpperCase();

  if (command == "PING") {
    Serial1.println("PONG");
    return;
  }

  if (command == "TRIGGER") {
    emitTriggerPulse(20);
    Serial1.println("TRIGGERED");
    return;
  }

  if (command.startsWith("PULSE ")) {
    uint32_t durationMs = command.substring(6).toInt();
    if (durationMs == 0 || durationMs > 1000) {
      Serial1.println("ERROR pulse duration must be 1-1000 ms");
      return;
    }
    emitTriggerPulse(durationMs);
    Serial1.printf("PULSE %lu\n", static_cast<unsigned long>(durationMs));
    return;
  }

  Serial1.println("ERROR commands: PING, TRIGGER, PULSE <1-1000>");
}
}  // namespace

void setup() {
  pinMode(kTriggerPin, OUTPUT);
  digitalWrite(kTriggerPin, LOW);

  Serial.begin(kBaudRate);  // USB debug console while flashing.
  Serial1.begin(kBaudRate, SERIAL_8N1, kPiRxPin, kPiTxPin);
  Serial.println("CyberTrace target ready");
}

void loop() {
  if (Serial1.available()) {
    handleCommand(Serial1.readStringUntil('\n'));
  }
}
