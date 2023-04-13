from machine import Pin
import time
import micropython
import rp2
from micropython import const
import array
import uctypes

constants = array.array("L", [
    0x50200000, # PIO0_CTRL
    0x50200004, # PIO0_FIFO
    0b01010101000011110101010100001111, # pattern to write to PIO0_OUT
    0x50200010, # PIO0_OUT
])


@micropython.asm_thumb
def loop(r0):
    ldr(r1, [r0, 0x00]) # r1 now has the address of the PIO_CTRL register
    mov(r2, 0x01)
    str(r2, [r1, 0x00]) # activate the PIO state machine 0
    lsl(r2, r2, 16) # r2 is bit 16
    ldr(r4, [r0, 0x0c]) # r4 now has the adddress of the TXF0 register
    ldr(r5, [r0, 0x08]) # r5 now has the pattern to write to the PIO_OUT register
    ldr(r1, [r0, 0x04]) # r1 now has the address of the PIO_FIFO register
    label(LOOP)
    ldr(r3, [r1, 0x00]) # r3 now has the value of the PIO_FIFO register
    #and_(r3, r3, r2) # r3 is now masked with r2
    #cmp(r3, r2) # compare the value of the PIO_FIFO register with the value of r2
    lsl(r3, r3, 15)
    lsr(r3, r3, 31)
    cmp(r3, 0x01)
    beq(LOOP) # the bit is set so the queue is full
    str(r5, [r4, 0x00]) # write the pattern to the PIO_OUT register
    b(LOOP) # loop back to the beginning




@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32)
def write_pixels():
    out(pins, 1)
    set(x, 31)
    label("loop")
    jmp(x_dec, "loop") [31]


sm = rp2.StateMachine(0, write_pixels, freq=2000, out_base=Pin(25))
loop(uctypes.addressof(constants))



    

