# PicoVGA

main.py is a micropython program which creates a frame and displays it over vga. Once it is started it doesn't use any cpu cores to run. It is entirely contained within DMA and PIO logic.

old.py is a failed attempt at using assembly before I found DMA.

blink.py, blink_dma.py and blink_dma_array.py are various tests at blinking the onboard led for testing.
