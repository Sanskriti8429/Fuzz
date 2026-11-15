#pragma once
// Fusion rule of the Fuzz unit. Pure C++ (no Arduino calls) so it can be tested on a PC against demo/simulator.py.
#include <math.h>

namespace fuzz {

constexpr float LIM_RF = 0.8f;       // normalised RF detector level
constexpr float LIM_LEAK = 30.0f;    // leakage current, mA
constexpr float LIM_DIDT = 1.0f;     // normalised di/dt level (1.0 = comparator fired)
constexpr float TEMP_WARN = 40.0f;   // degrees C, score is 0 here
constexpr float TEMP_TRIP = 80.0f;   // degrees C, score is 1 here
constexpr float V_MIN = 207.0f;      // +-10% of 230 V
constexpr float V_MAX = 253.0f;
constexpr float WARN_AVG = 0.35f;    // a channel counts as raised when its 5-reading average passes 35% of its limit
constexpr float HARD_WARN = 0.8f;    // a single channel at 80% of its limit also warns
constexpr float HOLD_S = 10.0f;      // a warning is held for 10 s so it does not flicker
constexpr int WINDOW = 5;
constexpr int NCH = 4;               // rf, leak, didt, temp

enum State { NORMAL = 0, WARNING = 1, TRIP = 2 };

struct Reading {
  float rf, leak_ma, didt, temp_c, volt;
};

class Fusion {
 public:
  // Call once per second with that second's readings. t is a time in seconds.
  State update(const Reading& r, float t) {
    float now[NCH] = {r.rf / LIM_RF, r.leak_ma / LIM_LEAK, r.didt / LIM_DIDT, (r.temp_c - TEMP_WARN) / (TEMP_TRIP - TEMP_WARN)};
    for (int c = 0; c < NCH; c++) win_[head_][c] = now[c];
    head_ = (head_ + 1) % WINDOW;
    if (n_ < WINDOW) n_++;

    int raised = 0;
    for (int c = 0; c < NCH; c++) {
      float sum = 0;
      for (int i = 0; i < n_; i++) sum += win_[i][c];     // the buffer holds the last n_ values (order does not matter for a mean)
      if (sum / n_ >= WARN_AVG) raised++;
    }
    float mx = now[0];
    bool anyTrip = false;
    for (int c = 0; c < NCH; c++) {
      if (now[c] > mx) mx = now[c];
      if (now[c] >= 1.0f) anyTrip = true;
    }
    bool voltBad = !(r.volt >= V_MIN && r.volt <= V_MAX);

    State s;
    if (tripped_ || anyTrip) s = TRIP;
    else if (raised >= 2 || mx >= HARD_WARN || voltBad) s = WARNING;
    else s = NORMAL;

    if (s == WARNING) warnUntil_ = t + HOLD_S;
    else if (s == NORMAL && t < warnUntil_) s = WARNING;
    if (s == TRIP) tripped_ = true;
    return s;
  }
  void forceTrip() { tripped_ = true; }
  void setTripped(bool v) { tripped_ = v; }
  bool tripped() const { return tripped_; }

 private:
  float win_[WINDOW][NCH] = {};
  int n_ = 0, head_ = 0;
  bool tripped_ = false;
  float warnUntil_ = -1.0f;
};

}  // namespace fuzz
