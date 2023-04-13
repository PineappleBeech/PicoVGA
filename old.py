from machine import Pin
import time
import micropython
import rp2
from micropython import const
import array
import uctypes
import machine

FREQUENCY = 60 * 800 * 525 * 10 # 60Hz * 800 pixels * 525 lines * 10 clocks per pixel

machine.freq(FREQUENCY)

constants = array.array("L", [
    0x50200000, # PIO0_CTRL
    0x0000ffff, # pattern to write to PIO0_OUT
    525, # height

])

# offsets from the base address of the array
PATTERN = const(0x04)
HEIGHT = const(0x08)

# offsets from the base address of the PIO0_CTRL register
PIO0_CTRL = const(0x00)
PIO0_FIFO = const(0x04)
PIO0_TXF0 = const(0x10)
PIO0_TXF1 = const(0x14)


# r0 is for the base address of the array
# r1 is for the address of the PIO_CTRL register, other addresses are calculated from this
# r2 is to start the state machine, then horizontal position in multiples of 16
# r3 is for the vertical position
# r4 is for the height
# r5 is for the pattern to write to the PIO_OUT register
# r6 is for temporary storage of the colour
# r7 is for temporary storage

@micropython.asm_thumb
def loop(r0):
    ldr(r1, [r0, 0x00]) # r1 = PIO0_CTRL address

    mov(r2, 0x03) # set r2 to 0x01
    str(r2, [r1, PIO0_CTRL]) # activate the PIO state machine 0 and 1
    lsl(r2, r2, 8)
    str(r2, [r1, PIO0_CTRL]) # sync the PIO state machines

    ldr(r5, [r0, PATTERN]) # r5 now has the pattern to write to the PIO0_TXF0 register
    ldr(r4, [r0, HEIGHT]) # r4 = height

    label(LOOP_START)

    mov(r2, 0x00) # reset horizontal position
    mov(r3, 0x00) # reset vertical position

    label(VERTICAL_SYNC)

    bl(BLOCK_UNTIL_SPACE) # block until there is space in the FIFO

    mov(r6, 0x00) # r6 = colour
    mov(r7, 0x02) # r7 = vertical sync
    str(r6, [r1, PIO0_TXF0]) # write the pattern to the PIO0_TXF0 register
    str(r7, [r1, PIO0_TXF1]) # write the pattern to the PIO0_TXF1 register

    add(r2, r2, 0x01) # increment horizontal position
    cmp(r2, 0x32) # compare horizontal position with width

    bne(VERTICAL_SYNC) # loop back if not at end of line

    add(r3, r3, 0x01) # increment vertical position
    cmp(r3, 0x02) # compare vertical position with sync height

    bne(VERTICAL_SYNC) # loop back if not at end of line

    label(VERTICAL_BACK_PORCH)
    label(VBP_HSYNC)

    bl(BLOCK_UNTIL_SPACE) # block until there is space in the FIFO
    
    mov(r6, 0x00) # r6 = colour
    mov(r7, 0x01) # r7 = horizontal sync
    str(r6, [r1, PIO0_TXF0]) # write the pattern to the PIO0_TXF0 register
    str(r7, [r1, PIO0_TXF1]) # write the pattern to the PIO0_TXF1 register

    add(r2, r2, 0x01) # increment horizontal position

    cmp(r2, 0x06) # compare horizontal position with width of sync

    bne(VBP_HSYNC) # loop back if not at end of line

    label(VBP_HBP)

    bl(BLOCK_UNTIL_SPACE) # block until there is space in the FIFO

    mov(r6, 0x00) # r6 = colour
    mov(r7, 0x00) # r7 = no sync
    str(r6, [r1, PIO0_TXF0]) # write the pattern to the PIO0_TXF0 register
    str(r7, [r1, PIO0_TXF1]) # write the pattern to the PIO0_TXF1 register

    add(r2, r2, 0x01) # increment horizontal position

    cmp(r2, 0x32) # compare horizontal position with width of rest of line

    bne(VBP_HBP) # loop back if not at end of line

    add(r3, r3, 0x01) # increment vertical position

    cmp(r3, r4) # compare vertical position with height of screen

    bne(VERTICAL_BACK_PORCH) # loop back if not at end of line

    b(LOOP_START) # loop back to the beginning

    # funtion to block until there is space in the FIFO
    # uses r7 as a temporary register
    label(BLOCK_UNTIL_SPACE)
    ldr(r7, [r1, PIO0_FIFO]) # r7 = PIO_FIFO value
    lsl(r7, r7, 15)
    lsr(r7, r7, 31) # filter to get emptyness
    cmp(r7, 0x01)
    beq(BLOCK_UNTIL_SPACE) # the queue is full
    bx(lr) # return to the caller



# only one colour for now
# 16 pixels at a time, 160 cycles per input
# 10 cycles per pixel
# sets on 1st cycle, 11th cycle and so on
@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=16)
def write_colour():
    out(pins, 1) [7]            # 8
    set(y, 15)                  # 1
    label("loop")
    nop()                       # 15
    out(pins, 1) [7]            # 8 * 15 = 120
    jmp(y_dec, "loop")          # 16
                                # 8 + 1 + 15 + 120 + 16 = 160




# LSB is horizontal sync, MSB is vertical sync
# 16 pixels at a time, 160 cycles per input
# sets on 1st cycle
@rp2.asm_pio(out_init=(rp2.PIO.OUT_LOW, rp2.PIO.OUT_LOW), autopull=True, pull_thresh=2)
def write_sync():
    out(pins, 2)                # 1
    set(y, 3) [30]              # 31
    label("loop")           
    jmp(y_dec, "loop") [31]     # 32 * 4 = 128
                                # 1 + 31 + 128 = 160





sm = rp2.StateMachine(0, write_colour, freq=FREQUENCY, out_base=Pin(0))
sm2 = rp2.StateMachine(0, write_sync, freq=FREQUENCY, out_base=Pin(3))
loop(uctypes.addressof(constants))



    

