#pragma once
// ---- network -------------------------------------------------------------------------
#define WIFI_SSID "Airtel_sans_2533"
#define WIFI_PASS "Air@52761"
#define BACKEND_URL "http://192.168.1.10:5000/api/telemetry"   // the PC running backend\app.py
#define UNIT_ID "fuzz-01"

// ---- pins (from the KiCad schematic) ---------------------------------------------------
#define PIN_RF 34        // RF_OUT
#define PIN_LEAK 35      // LEAK_OUT
#define PIN_DIDT 32      // DIDT_OUT, comparator output, high at rest, low on a fault
#define PIN_TEMP 33      // TEMP_OUT
#define PIN_VOLT 36      // VOLT_OUT (ZMPT101B module)
#define PIN_INTEG 39     // PROPOSED: output of U3A (di/dt integrator). Not in the schematic yet.
#define PIN_RELAY 26
#define PIN_BUZZER 25

// ---- options ---------------------------------------------------------------------------
#define USE_INTEGRATOR 0          // 1 only after U3A's output is wired to IO39: enables appliance features and RF-to-di/dt level
#define RELAY_ON_LEVEL HIGH       // level that closes the relay (supply on); check your relay module
#define RELAY_OFF_LEVEL LOW

// ---- calibration (PLACEHOLDERS: measure on hardware and replace) -------------------------
#define RF_BASE_MV 0.0f           // detector output with no arc
#define RF_FULL_MV 1800.0f        // detector output that counts as 1.0 (rail limit of the LM358 on 3.3 V is about 1.8 V)
#define LEAK_MV_PER_MA 2.5f       // peak-to-peak mV at LEAK_OUT per mA of leakage (SPICE: about 75 mV for 30 mA)
#define VOLT_V_PER_MV 0.35f       // mains volts RMS per mV RMS at VOLT_OUT (adjust with the module's trimmer)
#define DIDT_FULL_MV 1800.0f      // integrator output that counts as 1.0
#define RF_REL_OFFSET_DB 0.0f     // aligns the RF-to-di/dt level with the training data (needs a calibration run)
#define NTC_BETA 3950.0f          // assumed
#define NTC_R25 10000.0f
#define NTC_R_FIXED 10000.0f      // bottom resistor of the divider; NTC is on the 3.3 V side
#define VCC 3.3f
