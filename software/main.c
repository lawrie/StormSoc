#include <stdint.h>

#include "generated/soc.h"

void main() {
	puts("StormSoc\n");

	LED_GPIO->oe = 1;
	LED_GPIO->out = 0;
	SEG70->val = 0x123;

	while(1) {
		LED_GPIO->out = LED_GPIO->out + 1;
		for(int i=0;i<100000;i++) asm volatile ("");
		puts("Hello\n");
	};
}