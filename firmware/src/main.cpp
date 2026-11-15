// Fuzz unit firmware (ESP32, Arduino framework).
// NOT YET TESTED ON HARDWARE. The fusion rule and the feature maths are tested on a PC (see host_test/);
// ADC scaling, timing and the relay polarity must be checked on the real board.
#include <Arduino.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <time.h>

#include "config.h"
#include "shape_features.h"
#include "fusion.h"

using namespace fuzz;

static Fusion fusion;
static Preferences prefs;
static volatile bool didtFired = false;   // set by the comparator interrupt
static volatile bool relayOpen = false;

// Network hand-off: the sensing loop writes one JSON string, the network task sends it.
static char outJson[900];
static volatile bool outReady = false;

// ---------------------------------------------------------------------------------------------
// Relay and trip
// ---------------------------------------------------------------------------------------------
void IRAM_ATTR onDidt() {                 // fastest path: cut the supply inside the interrupt
  digitalWrite(PIN_RELAY, RELAY_OFF_LEVEL);
  relayOpen = true;
  didtFired = true;
}

static void openRelay() {
  digitalWrite(PIN_RELAY, RELAY_OFF_LEVEL);
  relayOpen = true;
  fusion.forceTrip();
  prefs.putBool("tripped", true);          // stays tripped after a power cycle until you send 'r' on the serial port
}

static void resetTrip() {
  fusion.setTripped(false);
  prefs.putBool("tripped", false);
  didtFired = false;
  relayOpen = false;
  digitalWrite(PIN_RELAY, RELAY_ON_LEVEL);
  Serial.println("reset: relay closed");
}

// ---------------------------------------------------------------------------------------------
// Measurements
// ---------------------------------------------------------------------------------------------
struct Window { float mean, rms, pp; };

// Sample one pin for about one mains cycle (20 ms at 50 Hz) and return mean, AC RMS and peak-to-peak in mV.
static Window sampleWindow(int pin, uint32_t duration_us = 20000) {
  double sum = 0, sq = 0;
  int n = 0;
  float lo = 1e9f, hi = -1e9f;
  uint32_t t0 = micros();
  while (micros() - t0 < duration_us) {
    float v = analogReadMilliVolts(pin);
    sum += v; sq += (double)v * v; n++;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  Window w{0, 0, 0};
  if (n > 0) {
    w.mean = sum / n;
    double var = sq / n - (double)w.mean * w.mean;
    w.rms = var > 0 ? sqrt(var) : 0;
    w.pp = hi - lo;
  }
  return w;
}

static float readMilliVolts(int pin, int n) {
  double s = 0;
  for (int i = 0; i < n; i++) s += analogReadMilliVolts(pin);
  return s / n;
}

static float readTempC() {                  // NTC on the 3.3 V side, fixed resistor to ground
  float v = readMilliVolts(PIN_TEMP, 16) / 1000.0f;
  if (v < 0.02f || v > VCC - 0.02f) return NAN;
  float rn = NTC_R_FIXED * (VCC / v - 1.0f);
  float invT = 1.0f / 298.15f + logf(rn / NTC_R25) / NTC_BETA;
  return 1.0f / invT - 273.15f;
}

static float clamp01(float x) { return x < 0 ? 0 : (x > 1.5f ? 1.5f : x); }

#if USE_INTEGRATOR
// Average 8 mains cycles of the di/dt integrator output, each started at a rising zero crossing of the mains
// voltage, 500 samples per cycle (40 us apart at 50 Hz). TODO on hardware: check that one analogReadMilliVolts()
// call is fast enough for a 40 us spacing, otherwise lower the number of samples or use continuous ADC mode.
static bool captureCycle(float* acc, float biasMv) {
  uint32_t t0 = micros();
  float prev = analogReadMilliVolts(PIN_VOLT);
  bool found = false;
  while (micros() - t0 < 60000) {
    float cur = analogReadMilliVolts(PIN_VOLT);
    if (prev < biasMv && cur >= biasMv) { found = true; break; }
    prev = cur;
  }
  if (!found) return false;
  uint32_t start = micros();
  for (int i = 0; i < CYCLE_N; i++) {
    uint32_t next = start + (uint32_t)i * 40;
    while ((int32_t)(micros() - next) < 0) {}
    acc[i] += analogReadMilliVolts(PIN_INTEG) / 1000.0f;
  }
  return true;
}

static bool captureFeatures(float biasMv, float* feat) {
  static float acc[CYCLE_N];
  for (int i = 0; i < CYCLE_N; i++) acc[i] = 0;
  int ok = 0;
  for (int c = 0; c < 8; c++) if (captureCycle(acc, biasMv)) ok++;
  if (ok < 4) return false;
  for (int i = 0; i < CYCLE_N; i++) acc[i] /= ok;
  shape_features(acc, CYCLE_N, feat);
  return true;
}
#endif

// ---------------------------------------------------------------------------------------------
// Network task (core 0), so a slow HTTP call never delays the trip logic on core 1
// ---------------------------------------------------------------------------------------------
static void networkTask(void*) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  configTime(0, 0, "pool.ntp.org");
  for (;;) {
    if (WiFi.status() != WL_CONNECTED) { delay(500); continue; }
    if (outReady) {
      HTTPClient http;
      http.setTimeout(1500);
      if (http.begin(BACKEND_URL)) {
        http.addHeader("Content-Type", "application/json");
        http.POST((uint8_t*)outJson, strlen(outJson));
        http.end();
      }
      outReady = false;
    }
    delay(20);
  }
}

// ---------------------------------------------------------------------------------------------
// Setup and loop
// ---------------------------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_BUZZER, LOW);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_RF, ADC_11db);
  analogSetPinAttenuation(PIN_LEAK, ADC_11db);
  analogSetPinAttenuation(PIN_TEMP, ADC_11db);
  analogSetPinAttenuation(PIN_VOLT, ADC_11db);
#if USE_INTEGRATOR
  analogSetPinAttenuation(PIN_INTEG, ADC_11db);
#endif

  prefs.begin("fuzz", false);
  bool wasTripped = prefs.getBool("tripped", false);
  if (wasTripped) {
    fusion.setTripped(true);
    relayOpen = true;
    digitalWrite(PIN_RELAY, RELAY_OFF_LEVEL);
    Serial.println("tripped before the last restart: relay stays open. Send 'r' to reset.");
  } else {
    digitalWrite(PIN_RELAY, RELAY_ON_LEVEL);
  }
  pinMode(PIN_DIDT, INPUT_PULLUP);          // comparator output; the pull-up is only a safety net
  attachInterrupt(digitalPinToInterrupt(PIN_DIDT), onDidt, FALLING);
  xTaskCreatePinnedToCore(networkTask, "net", 8192, nullptr, 1, nullptr, 0);
}

static const char* STATE_NAME[] = {"NORMAL", "WARNING", "TRIP"};

void loop() {
  static uint32_t lastSecond = 0, lastFeat = 0;
  static float aggRf = 0, aggLeak = 0, aggDidt = 0, voltV = 230.0f, tempC = 25.0f, voltBias = 1650.0f;
  static float rfMv = 0, didtMv = 0;
  static float feat[N_FEATURES];
  static bool haveFeat = false;
  static State state = NORMAL;

  if (Serial.available() && Serial.read() == 'r') resetTrip();

  // ---- fast tick (about 45 ms): one mains cycle each of leakage and voltage, plus RF and di/dt ----
  rfMv = readMilliVolts(PIN_RF, 4);
  float rf = clamp01((rfMv - RF_BASE_MV) / (RF_FULL_MV - RF_BASE_MV));
  Window lk = sampleWindow(PIN_LEAK);
  float leak = lk.pp / LEAK_MV_PER_MA;
  Window vw = sampleWindow(PIN_VOLT);
  voltBias = vw.mean;
  voltV = vw.rms * VOLT_V_PER_MV;
  float didt = didtFired ? 1.0f : 0.0f;
#if USE_INTEGRATOR
  Window iw = sampleWindow(PIN_INTEG, 5000);
  didtMv = iw.mean + iw.pp;
  if (!didtFired) didt = clamp01(didtMv / DIDT_FULL_MV);
#endif
  if (rf > aggRf) aggRf = rf;
  if (leak > aggLeak) aggLeak = leak;
  if (didt > aggDidt) aggDidt = didt;

  // instantaneous limits: do not wait for the one-second tick
  if (!fusion.tripped() && (rf >= 1.0f || leak >= LIM_LEAK || didt >= 1.0f)) openRelay();
  if (relayOpen && !fusion.tripped()) openRelay();      // the interrupt already opened the relay: latch it

  // ---- one-second tick: fusion, outputs, telemetry ----
  uint32_t now = millis();
  if (now - lastSecond >= 1000) {
    lastSecond = now;
    float t = readTempC();
    if (!isnan(t)) tempC = t;
    Reading r{aggRf, aggLeak, aggDidt, tempC, voltV};
    state = fusion.update(r, now / 1000.0f);
    if (state == TRIP && !relayOpen) openRelay();

    // buzzer: steady on trip, short beep every second on warning
    if (state == TRIP) digitalWrite(PIN_BUZZER, HIGH);
    else if (state == WARNING) digitalWrite(PIN_BUZZER, HIGH);   // switched off again below after 100 ms
    else digitalWrite(PIN_BUZZER, LOW);

#if USE_INTEGRATOR
    if (state != TRIP && now - lastFeat >= 5000) {
      lastFeat = now;
      haveFeat = captureFeatures(voltBias, feat);
    }
#endif

    if (!outReady) {
      char iso[32] = "";
      struct tm tmv;
      if (getLocalTime(&tmv, 0)) strftime(iso, sizeof(iso), "%Y-%m-%dT%H:%M:%SZ", &tmv);
      bool dead = relayOpen;                // after a trip the circuit is dead, as in the simulator
      int n = snprintf(outJson, sizeof(outJson),
                       "{\"unit_id\":\"%s\",\"time\":\"%s\",\"state\":\"%s\",\"relay\":\"%s\","
                       "\"rf\":%.3f,\"leak_ma\":%.2f,\"didt\":%.3f,\"temp_c\":%.2f,\"volt\":%.1f",
                       UNIT_ID, iso, STATE_NAME[state], relayOpen ? "OPEN" : "CLOSED",
                       dead ? 0.0f : aggRf, dead ? 0.0f : aggLeak, dead ? 0.0f : aggDidt, tempC, dead ? 0.0f : voltV);
#if USE_INTEGRATOR
      if (haveFeat && !dead) {
        n += snprintf(outJson + n, sizeof(outJson) - n, ",\"appliance_features\":[");
        for (int i = 0; i < N_FEATURES; i++) n += snprintf(outJson + n, sizeof(outJson) - n, "%s%.5f", i ? "," : "", feat[i]);
        n += snprintf(outJson + n, sizeof(outJson) - n, "]");
        if (aggRf > 0.15f && rfMv > 1.0f && didtMv > 1.0f) {
          float relDb = 20.0f * log10f(rfMv) - 20.0f * log10f(didtMv) + RF_REL_OFFSET_DB;
          n += snprintf(outJson + n, sizeof(outJson) - n, ",\"rf_rel_db\":%.2f", relDb);
        }
      }
#endif
      snprintf(outJson + n, sizeof(outJson) - n, "}");
      outReady = true;
    }
    Serial.printf("%s rf=%.2f leak=%.1fmA didt=%.2f temp=%.1fC volt=%.0fV relay=%s\n", STATE_NAME[state], aggRf, aggLeak,
                  aggDidt, tempC, voltV, relayOpen ? "open" : "closed");
    aggRf = aggLeak = aggDidt = 0;
    didtFired = false;                       // the latch lives in fusion/prefs; the flag is per second
  }
  if (state == WARNING && millis() - lastSecond > 100) digitalWrite(PIN_BUZZER, LOW);
}
