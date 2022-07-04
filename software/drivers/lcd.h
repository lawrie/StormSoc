#ifndef LCD_H
#define LCD_H

#include <stdint.h>

typedef struct __attribute__((packed)) {
	uint32_t ch;
	uint32_t x;
	uint32_t y;
	uint32_t color;
} lcd_regs_t;

#endif
