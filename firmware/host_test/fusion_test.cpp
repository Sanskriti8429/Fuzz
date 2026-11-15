// Reads rows "t rf leak didt temp volt" from stdin, prints the state for each row.
#include <cstdio>
#include "../include/fusion.h"
int main() {
  fuzz::Fusion f;
  float t, rf, lk, d, tp, v;
  while (scanf("%f %f %f %f %f %f", &t, &rf, &lk, &d, &tp, &v) == 6) {
    fuzz::Reading r{rf, lk, d, tp, v};
    printf("%d\n", (int)f.update(r, t));
  }
}
