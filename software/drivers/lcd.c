#include "lcd.h"

void lcd_putc(volatile lcd_regs_t *lcd, int x, int y, char c) {
    lcd->x = x;
    lcd->y = y;
	lcd->ch = c;
}

void lcd_puts(volatile lcd_regs_t *lcd, int x, int y, const char *s) {
	while (*s != 0)
		lcd_putc(lcd, x++, y, *s++);
}