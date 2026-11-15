// Reads 500 floats per line from stdin, prints the 17 features per line.
#include <cstdio>
#include "../include/shape_features.h"
int main() {
  static float x[500], out[17];
  for (;;) {
    for (int i = 0; i < 500; i++) if (scanf("%f", &x[i]) != 1) return 0;
    fuzz::shape_features(x, 500, out);
    for (int i = 0; i < 17; i++) printf("%.7g%c", out[i], i == 16 ? '\n' : ' ');
  }
}
