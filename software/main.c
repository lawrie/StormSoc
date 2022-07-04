#include <stdint.h>

#include "generated/soc.h"

void main() {
	puts("StormSoc\n");

	LED_GPIO->oe = 1;
	LED_GPIO->out = 0;

    uint16_t color = 0;

	while(1) {
		LED_GPIO->out = LED_GPIO->out + 1;
		SEG70->val = color >> 4;
		LCD0->color = color;
		color += 16;
		for(int i=0;i<100000;i++) asm volatile ("");
		puts("Hello\n");
	};
}