// SPDX-License-Identifier: BSD-2-Clause-Patent
// Private P1 test ABI, carried as chosen/gunyah-probe in Apple DT encoding.
// This is not an XNU platform device tree schema.
#ifndef GUNYAH_PROBE_PLATFORM_H
#define GUNYAH_PROBE_PLATFORM_H
typedef struct {
  unsigned long long version;
  unsigned long long uart;
  unsigned long long gicd;
  unsigned long long gicr;
  unsigned long long ram_base;
  unsigned long long ram_size;
  unsigned long long fb_base;
  unsigned long long fb_size;
  unsigned long long timer_irq;
  unsigned long long counter_freq;
} PROBE_PLATFORM;
#endif
