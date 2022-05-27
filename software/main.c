#include <stdint.h>

#include "generated/soc.h"

volatile gpio_regs_t *gpio;

void main() {
	puts("StormSoc\n");

	gpio->oe = 1;
	gpio->out = 1;
	while(1) {
		gpio->out = ~gpio->out;
		for(int i=0;i<10000;i++) asm volatile ("");
		puts("Hello\n");
	};
}