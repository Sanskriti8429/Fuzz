#pragma once
// Shape features of one averaged mains cycle of the di/dt integrator output.
// Same definition as shape_features() in ml/baseline_appliance_proxy.py (17 values):
// harmonics 2..15 relative to the fundamental, crest factor, THD, conduction duty.
#include <math.h>

namespace fuzz {

constexpr int CYCLE_N = 500;     // samples per mains cycle
constexpr int N_FEATURES = 17;

inline void shape_features(const float* x, int n, float* out) {
  const double TWO_PI = 6.283185307179586;
  double sp[15];
  for (int k = 1; k <= 15; k++) {
    double re = 0, im = 0;
    for (int i = 0; i < n; i++) {
      double a = TWO_PI * k * i / n;
      re += x[i] * cos(a);
      im -= x[i] * sin(a);
    }
    sp[k - 1] = sqrt(re * re + im * im);
  }
  double sq = 0, amax = 0;
  for (int i = 0; i < n; i++) {
    sq += (double)x[i] * x[i];
    double a = fabs((double)x[i]);
    if (a > amax) amax = a;
  }
  double rms = sqrt(sq / n) + 1e-9;
  double thdSum = 0;
  for (int k = 1; k < 15; k++) {
    out[k - 1] = (float)(sp[k] / (sp[0] + 1e-9));        // harmonics 2..15
    thdSum += sp[k] * sp[k];
  }
  int conducting = 0;
  for (int i = 0; i < n; i++) if (fabs((double)x[i]) > 0.05 * amax) conducting++;
  out[14] = (float)(amax / rms);                          // crest
  out[15] = (float)(sqrt(thdSum) / (sp[0] + 1e-9));       // THD
  out[16] = (float)((double)conducting / n);              // duty
}

}  // namespace fuzz
