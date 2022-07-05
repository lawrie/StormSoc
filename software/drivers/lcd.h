#ifndef LCD_H
#define LCD_H

#include <stdint.h>

typedef struct __attribute__((packed)) {
	uint32_t ch;
	uint32_t x;
	uint32_t y;
	uint32_t color;
} lcd_regs_t;

void lcd_putc(volatile lcd_regs_t *lcd, int x, int y,  char c);
void lcd_puts(volatile lcd_regs_t *lcd, int x, int y,  const char *s);

#endif
