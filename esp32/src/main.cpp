#include <Arduino.h>

namespace {

constexpr int kTriggerPin = 4;
constexpr int kPiRxPin = 18;
constexpr int kPiTxPin = 17;
constexpr uint32_t kBaudRate = 115200;

// Amplified-leakage output pins: eight free, broken-out ESP32-S3 GPIOs with
// nothing wired to them. LEAKLOOP toggles only the pins matching SET bits of
// the target byte, so the data-dependent switching current on the VCC rail
// (measured through the shunt by the ADS1115) scales with the byte's Hamming
// weight. This amplifies microsecond-scale crypto leakage into the
// millisecond timescale a slow ADC can actually sample -- the CPA methodology
// is unchanged, only the signal magnitude is boosted.
constexpr int kLeakPins[8] = {5, 6, 7, 8, 9, 10, 11, 12};
constexpr int kLeakDummyPin = 13;     // held low; absorbs clear-bit work
constexpr uint32_t kLeakIter = 6000;  // ~per-byte window length; tune vs ADC rate

// ──────────────── ChaCha20 state ────────────────
uint32_t chacha_key[8] = {
    0xDEADBEEF, 0xCAFEBABE, 0x13371337, 0xA5A5A5A5,
    0x5A5A5A5A, 0xF0F0F0F0, 0x0F0F0F0F, 0xBAADF00D};
uint32_t chacha_nonce[3] = {0, 0, 0};
static constexpr uint32_t kConstants[4] = {
    0x61707865, 0x3320646e, 0x79622d32, 0x6b206574};

// ──────────────── Defense flags ────────────────
bool masking_enabled = false;
bool constant_time_enabled = false;
bool nonce_enabled = false;
int last_seen_counter = -1;

// ──────────────── Auth secret (timing attack target) ────────────────
const uint8_t auth_secret[] = {'K', '3', 'Y', '!'};
constexpr size_t kSecretLen = sizeof(auth_secret);

// ──────────────── Kyber (post-quantum) side-channel target ────────────────
// The leaking operation in Kyber is the NTT-domain pointwise multiplication of
// the secret key with ciphertext-derived data: t = s_hat * u mod q. We hold one
// secret NTT coefficient and, on KYBERLEAK <u>, compute the real product and
// amplify HW(t) the same way LEAKLOOP does, so a CPA recovers s_hat on the slow
// ADC. This is genuine Kyber arithmetic (mod q=3329) with a real secret, i.e.
// a real PQC key-recovery target, not a leakage mock-up.
constexpr uint16_t kKyberQ = 3329;
uint16_t kyber_s_hat = 1234;  // secret NTT coefficient under attack

// ──────────────── ChaCha20 primitives ────────────────

inline uint32_t rotl32(uint32_t v, int n) {
    return (v << n) | (v >> (32 - n));
}

void quarter_round(uint32_t state[16], int a, int b, int c, int d) {
    state[a] += state[b]; state[d] ^= state[a]; state[d] = rotl32(state[d], 16);
    state[c] += state[d]; state[b] ^= state[c]; state[b] = rotl32(state[b], 12);
    state[a] += state[b]; state[d] ^= state[a]; state[d] = rotl32(state[d], 8);
    state[c] += state[d]; state[b] ^= state[c]; state[b] = rotl32(state[b], 7);
}

void chacha20_block(const uint32_t key[8], uint32_t counter,
                    const uint32_t nonce[3], uint32_t out[16]) {
    uint32_t state[16];
    state[0]  = kConstants[0]; state[1]  = kConstants[1];
    state[2]  = kConstants[2]; state[3]  = kConstants[3];
    state[4]  = key[0]; state[5]  = key[1];
    state[6]  = key[2]; state[7]  = key[3];
    state[8]  = key[4]; state[9]  = key[5];
    state[10] = key[6]; state[11] = key[7];
    state[12] = counter;
    state[13] = nonce[0]; state[14] = nonce[1]; state[15] = nonce[2];

    uint32_t working[16];
    memcpy(working, state, sizeof(state));

    for (int i = 0; i < 10; i++) {
        quarter_round(working, 0, 4, 8,  12);
        quarter_round(working, 1, 5, 9,  13);
        quarter_round(working, 2, 6, 10, 14);
        quarter_round(working, 3, 7, 11, 15);
        quarter_round(working, 0, 5, 10, 15);
        quarter_round(working, 1, 6, 11, 12);
        quarter_round(working, 2, 7, 8,  13);
        quarter_round(working, 3, 4, 9,  14);
    }

    for (int i = 0; i < 16; i++)
        out[i] = working[i] + state[i];
}

// ──────────────── Helpers ────────────────

uint32_t hexToU32(const char *s) {
    return (uint32_t)strtoul(s, nullptr, 16);
}

void hexToBytes(const char *hex, uint8_t *out, size_t max_len) {
    size_t hex_len = strlen(hex);
    size_t byte_len = hex_len / 2;
    if (byte_len > max_len) byte_len = max_len;
    for (size_t i = 0; i < byte_len; i++) {
        char hi = hex[2 * i];
        char lo = hex[2 * i + 1];
        auto nibble = [](char c) -> uint8_t {
            if (c >= '0' && c <= '9') return c - '0';
            if (c >= 'a' && c <= 'f') return 10 + c - 'a';
            if (c >= 'A' && c <= 'F') return 10 + c - 'A';
            return 0;
        };
        out[i] = (nibble(hi) << 4) | nibble(lo);
    }
}

void emitTriggerPulse(uint32_t durationMs) {
    digitalWrite(kTriggerPin, HIGH);
    delay(durationMs);
    digitalWrite(kTriggerPin, LOW);
}

// ──────────────── Command handlers ────────────────

void handlePing() {
    Serial1.println("PONG");
}

void handleTrigger() {
    emitTriggerPulse(20);
    Serial1.println("TRIGGERED");
}

void handleEncrypt(const String &args) {
    uint32_t counter = hexToU32(args.c_str());

    digitalWrite(kTriggerPin, HIGH);
    uint32_t out[16];
    chacha20_block(chacha_key, counter, chacha_nonce, out);
    digitalWrite(kTriggerPin, LOW);

    char buf[9];
    for (int i = 0; i < 16; i++) {
        snprintf(buf, sizeof(buf), "%08x", out[i]);
        Serial1.print(buf);
    }
    Serial1.println();
}

void handleCheck(const String &args) {
    uint8_t candidate[64];
    size_t hex_len = args.length();
    size_t byte_len = hex_len / 2;
    if (byte_len > sizeof(candidate)) byte_len = sizeof(candidate);
    hexToBytes(args.c_str(), candidate, byte_len);

    bool accepted;

    // Per-byte work amplified to kByteCostUs so the early-exit timing leak is
    // measurable over UART jitter. On a bare 240MHz core a few byte-compares
    // differ by nanoseconds, far below what the Pi can resolve across the
    // serial link; a real system doing per-byte work (HMAC chunk, slow-bus
    // fetch) would differ by this order. The constant-time path below always
    // pays the full kSecretLen cost regardless of where the mismatch is.
    constexpr uint32_t kByteCostUs = 200;

    if (constant_time_enabled) {
        uint8_t diff = (byte_len != kSecretLen) ? 1 : 0;
        for (size_t i = 0; i < kSecretLen; i++) {
            uint8_t c = (i < byte_len) ? candidate[i] : 0;
            diff |= c ^ auth_secret[i];
            delayMicroseconds(kByteCostUs);
        }
        accepted = (diff == 0);
    } else {
        accepted = (byte_len == kSecretLen);
        for (size_t i = 0; i < byte_len && i < kSecretLen; i++) {
            delayMicroseconds(kByteCostUs);
            if (candidate[i] != auth_secret[i]) {
                accepted = false;
                break;
            }
        }
    }

    Serial1.println(accepted ? "OK" : "FAIL");
}

void handleCmd(const String &args) {
    int space = args.indexOf(' ');
    if (space < 0) {
        Serial1.println("ERR");
        return;
    }

    int counter = args.substring(0, space).toInt();
    String payload_hex = args.substring(space + 1);

    if (nonce_enabled && counter <= last_seen_counter) {
        Serial1.println("ERR");
        return;
    }

    if (counter > last_seen_counter)
        last_seen_counter = counter;

    Serial1.println("OK");
}

void handleSetKey(const String &args) {
    if (args.length() < 8) {
        Serial1.println("ERR");
        return;
    }
    chacha_key[0] = hexToU32(args.c_str());
    Serial1.println("OK");
}

void handleDefense(const String &args) {
    if (args.startsWith("MASKING ON"))        { masking_enabled = true;        Serial1.println("OK"); }
    else if (args.startsWith("MASKING OFF"))   { masking_enabled = false;       Serial1.println("OK"); }
    else if (args.startsWith("CTIME ON"))      { constant_time_enabled = true;  Serial1.println("OK"); }
    else if (args.startsWith("CTIME OFF"))     { constant_time_enabled = false; Serial1.println("OK"); }
    else if (args.startsWith("NONCE ON"))      { nonce_enabled = true;          Serial1.println("OK"); }
    else if (args.startsWith("NONCE OFF"))     { nonce_enabled = false;         Serial1.println("OK"); }
    else { Serial1.println("ERR"); }
}

void handleStatus() {
    Serial1.printf("masking=%d ctime=%d nonce=%d\n",
                   masking_enabled, constant_time_enabled, nonce_enabled);
}

void handleClock(const String &args) {
    int mhz = args.toInt();
    if (mhz == 80 || mhz == 160 || mhz == 240) {
        setCpuFrequencyMhz(mhz);
        Serial1.printf("CLK %d\n", mhz);
    } else {
        Serial1.println("ERR valid: 80, 160, 240");
    }
}

void handleLeakLoop(const String &args) {
    uint32_t counter = hexToU32(args.c_str());
    // Real ChaCha20 first-round intermediate: d = counter ^ (const0 + key0).
    uint32_t a = (kConstants[0] + chacha_key[0]) & 0xFFFFFFFF;
    uint32_t d = counter ^ a;

    // First-order Boolean masking: leak (d ^ mask) with a fresh hardware-random
    // mask per call. The masked value's Hamming weight is statistically
    // independent of d (hence of key0), so univariate CPA correlating against
    // HW(d) collapses to the noise floor. mask = 0 when masking is disabled,
    // leaving the unprotected leakage intact.
    uint32_t mask = masking_enabled ? esp_random() : 0;
    uint32_t v = d ^ mask;

    digitalWrite(kTriggerPin, HIGH);
    for (int j = 0; j < 4; j++) {
        uint8_t b = (v >> (8 * j)) & 0xFF;
        for (uint32_t it = 0; it < kLeakIter; it++) {
            for (int k = 0; k < 8; k++) {
                if (b & (1 << k)) {
                    // set bit: real toggle on the shunt-measured rail
                    digitalWrite(kLeakPins[k], HIGH);
                    digitalWrite(kLeakPins[k], LOW);
                } else {
                    // clear bit: equal-cost dummy, no edge -> no dynamic current,
                    // so each phase takes constant time but current ~ HW(byte)
                    digitalWrite(kLeakDummyPin, LOW);
                    digitalWrite(kLeakDummyPin, LOW);
                }
            }
        }
    }
    digitalWrite(kTriggerPin, LOW);
    Serial1.println("LEAKDONE");
}

void handleKyberLeak(const String &args) {
    uint32_t u = hexToU32(args.c_str()) % kKyberQ;
    uint16_t t = (uint16_t)(((uint32_t)kyber_s_hat * u) % kKyberQ);  // leaking product

    // Amplify HW(t) over its 12 bits: each set bit toggles one leak pin per
    // iteration, so sustained current over the loop scales with HW(t). Single
    // phase -- one coefficient, one value.
    digitalWrite(kTriggerPin, HIGH);
    for (uint32_t it = 0; it < kLeakIter; it++) {
        for (int bit = 0; bit < 12; bit++) {
            if (t & (1 << bit)) {
                int pin = kLeakPins[bit & 7];
                digitalWrite(pin, HIGH);
                digitalWrite(pin, LOW);
            } else {
                digitalWrite(kLeakDummyPin, LOW);
                digitalWrite(kLeakDummyPin, LOW);
            }
        }
    }
    digitalWrite(kTriggerPin, LOW);
    Serial1.println("KYBERDONE");
}

void handleCommand(String command) {
    command.trim();

    if (command.equalsIgnoreCase("PING"))    { handlePing();   return; }
    if (command.equalsIgnoreCase("TRIGGER")) { handleTrigger(); return; }
    if (command.equalsIgnoreCase("STATUS"))  { handleStatus();  return; }

    int space = command.indexOf(' ');
    if (space < 0) {
        Serial1.println("ERR unknown command");
        return;
    }

    String verb = command.substring(0, space);
    String args = command.substring(space + 1);
    verb.toUpperCase();

    if      (verb == "ENCRYPT") handleEncrypt(args);
    else if (verb == "LEAKLOOP") handleLeakLoop(args);
    else if (verb == "KYBERLEAK") handleKyberLeak(args);
    else if (verb == "CHECK")   handleCheck(args);
    else if (verb == "CMD")     handleCmd(args);
    else if (verb == "SET_KEY") handleSetKey(args);
    else if (verb == "DEFENSE") handleDefense(args);
    else if (verb == "CLOCK")   handleClock(args);
    else if (verb == "PULSE") {
        uint32_t d = args.toInt();
        if (d >= 1 && d <= 1000) { emitTriggerPulse(d); Serial1.printf("PULSE %lu\n", (unsigned long)d); }
        else Serial1.println("ERR pulse 1-1000");
    }
    else Serial1.println("ERR unknown command");
}

}  // namespace

void setup() {
    pinMode(kTriggerPin, OUTPUT);
    digitalWrite(kTriggerPin, LOW);

    for (int k = 0; k < 8; k++) {
        pinMode(kLeakPins[k], OUTPUT);
        digitalWrite(kLeakPins[k], LOW);
    }
    pinMode(kLeakDummyPin, OUTPUT);
    digitalWrite(kLeakDummyPin, LOW);

    Serial.begin(kBaudRate);
    Serial1.begin(kBaudRate, SERIAL_8N1, kPiRxPin, kPiTxPin);
    Serial.println("CyberTrace target ready");
}

void loop() {
    if (Serial1.available()) {
        handleCommand(Serial1.readStringUntil('\n'));
    }
}
