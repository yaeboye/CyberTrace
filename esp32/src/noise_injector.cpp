#include <Arduino.h>

namespace {

constexpr int kLoadPin = 15;
constexpr uint32_t kBaudRate = 115200;

bool active = true;
unsigned long min_delay_us = 10000;
unsigned long max_delay_us = 80000;

void handleCommand(String command) {
    command.trim();
    command.toUpperCase();

    if (command == "PING") {
        Serial.println("PONG");
        return;
    }
    if (command == "START") {
        active = true;
        Serial.println("OK");
        return;
    }
    if (command == "STOP") {
        active = false;
        digitalWrite(kLoadPin, LOW);
        Serial.println("OK");
        return;
    }
    if (command.startsWith("SPEED ")) {
        int space2 = command.indexOf(' ', 6);
        if (space2 > 0) {
            min_delay_us = command.substring(6, space2).toInt();
            max_delay_us = command.substring(space2 + 1).toInt();
            if (min_delay_us < 10) min_delay_us = 10;
            if (max_delay_us < min_delay_us) max_delay_us = min_delay_us + 100;
            Serial.printf("SPEED %lu %lu\n", min_delay_us, max_delay_us);
        } else {
            Serial.println("ERR usage: SPEED <min_us> <max_us>");
        }
        return;
    }
    Serial.println("ERR commands: PING, START, STOP, SPEED <min> <max>");
}

}  // namespace

void setup() {
    pinMode(kLoadPin, OUTPUT);
    digitalWrite(kLoadPin, LOW);
    Serial.begin(kBaudRate);
    Serial.println("CyberTrace noise injector ready");
}

void loop() {
    if (Serial.available()) {
        handleCommand(Serial.readStringUntil('\n'));
    }

    if (active) {
        digitalWrite(kLoadPin, HIGH);
        delayMicroseconds(random(min_delay_us, max_delay_us));
        digitalWrite(kLoadPin, LOW);
        delayMicroseconds(random(min_delay_us, max_delay_us));
    }
}
