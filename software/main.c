#include <stdint.h>

#include "generated/soc.h"

void main() {
	puts("StormSoc\n");

	LED_GPIO->oe = 1;
	LED_GPIO->out = 1;
	while(1) {
		LED_GPIO->out = ~LED_GPIO->out;
		for(int i=0;i<10000;i++) asm volatile ("");
		puts("Hello\n");
	};
}