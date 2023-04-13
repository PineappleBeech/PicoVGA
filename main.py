from machine import Pin
import time
import micropython
import rp2
from micropython import const
import array
import uctypes
import machine
import framebuf

print("Hello, world!")

FREQUENCY = const(60 * 800 * 525 * 10) # 60Hz * 800 pixels * 525 lines * 10 clocks per pixel
machine.freq(FREQUENCY)

BIT_DEPTH = const(1) # 1 bit per pixel

VERT_SYNC = const(2) # 2 lines of vertical sync
VERT_BACK_PORCH = const(33) # 33 lines of vertical back porch
VERT_IMAGE = const(480) # 480 lines of image
VERT_FRONT_PORCH = const(10) # 10 lines of vertical front porch

HORZ_SYNC = const(96) # 96 pixels of horizontal sync
HORZ_BACK_PORCH = const(48) # 48 pixels of horizontal back porch
HORZ_IMAGE = const(640) # 640 pixels of image
HORZ_FRONT_PORCH = const(16) # 16 pixels of horizontal front porch

DMA_CHANNEL_BASE = const(0x50000000)
DMA_CH0 = const(DMA_CHANNEL_BASE + 0x00)
DMA_CH1 = const(DMA_CHANNEL_BASE + 0x40)
DMA_READ_ADDR = const(0x00)
DMA_WRITE_ADDR = const(0x04)
DMA_TRANS_COUNT = const(0x08)
DMA_CTRL_TRIG = const(0x0c)
DMA_CTRL = const(0x10)
DMA_READ_TRIG = const(0x3c)

DMA_ABORT = const(0x0444)


DREQ_PIO0_TX0 = const(0)

PIO0_CTRL = const(0x50200000)
PIO0_TXF0 = const(PIO0_CTRL + 0x10)

# these need to be in RAM so that the DMA can access them
constants = array.array("L", [
    0 # start address of bytearray for the DMA, will be set later

])

DMA_READ_TARGET_ADDR = uctypes.addressof(constants) + 0x00


# only one colour for now
# 10 cycles per pixel
# 10 * 800 = 8000 cycles per line
# 1st word is type of line

# HSYNC is bit 0, VSYNC is bit 1
# they are active low (0 for sync, 1 for image)

# little endian so bytes are reversed

# for VSYNC, send 0x1, 0x31e
# squashed into 0x000031e1
# pull 4, 28
VSYNC_LINE_LENGTH = const(4)
VSYNC_LINE_BYTES = bytes.fromhex("e1310000")

# for front/back porch, send 0x0, 0x1, 0x5e, 0x2e, 0x027f
# squashed into 0x002e5e10, 0x0000027f
# pull 4, 4, 8, 16, 32
PORCH_LINE_LENGTH = const(8)
PORCH_LINE_BYTES = bytes.fromhex("105e2e007f020000")

# for image, send 0x0, 0x0, 0x5e, 0x2e, 0x027f, 640 * bitdepth bits
# squashed into 0x002e5e00, 0x0000027f, 640 * bitdepth bits
# pull 4, 4, 8, 16, 32, 640 * bitdepth
IMAGE_LINE_LENGTH = const(8 + 80 * BIT_DEPTH) # 640 * bitdepth / 8 = 80 * bitdepth
IMAGE_LINE_PREFIX_LENGTH = const(8)
IMAGE_LINE_BYTES_PREFIX = bytes.fromhex("005e2e007f020000")

# outputs every 10 cycles on the 4th cycle, 4, 14, 24, etc
# each branch should be at the start within 6 cycles of its last output
# all the delaying loops delay for x + 1 cycles because they delay after completing the loop
# cycle count each instruction ends on is in the comment
@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, set_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH), autopull=True, pull_thresh=32, out_shiftdir=rp2.PIO.SHIFT_RIGHT, fifo_join=rp2.PIO.JOIN_TX)
def write_colour():
    label("start")

    out(x, 4) # 1 # 1 for vertical sync, 0 for porch/image
    jmp(not_x, "line") # 2

    label("vsync")

    out(x, 28) # 3 # get width of line - 2 (798 pixels)

    set(pins, 0b01) [5] # 9

    label("vsync_loop")
    jmp(x_dec, "vsync_loop") [9] # 7999 # 10 * 799 = 7990 cycles

    # no setting pins because they are either the same next line for will be set straight away

    jmp("start") # 8000

    label("line")

    out(y, 4) # 3 # 1 for porch, 0 for image

    label("hsync")

    set(pins, 0b10) # 4
    
    out(x, 8) [8] # 13 # get width of sync - 2 (94)

    label("hsync_loop")
    jmp(x_dec, "hsync_loop") [9] # 963 # 10 * 95 = 950 cycles

    set(pins, 0b11) # 964

    out(x, 16) # 965 # get width of back porch - 2 (46)

    label("back_porch_loop")
    jmp(x_dec, "back_porch_loop") [9] # 1435 # 10 * 47 = 470 cycles

    out(x, 32) # 1436 # get width of area - 1 (639)

    jmp(not_y, "image") [6] # 1443

    label("porch_line_loop")
    jmp(x_dec, "porch_line_loop") [9] # 7853 # 10 * 640 = 6400 cycles

    jmp("front_porch") # 7844

    label("image")

    label("image_line_loop")
    out(pins, 1)
    jmp(x_dec, "image_line_loop") [8] # 7853 # 9 * 640 + 640 = 6400 cycles

    mov(pins, null) # 7844

    label("front_porch")

    set(x, 14) [4] # 7849 # set width of front porch (16)

    label("front_porch_loop")
    jmp(x_dec, "front_porch_loop") [9] # 7999 # 10 * 15 = 150 cycles

    jmp("start") # 8000


@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, set_init=(rp2.PIO.OUT_HIGH, rp2.PIO.OUT_HIGH), autopull=True, autopush=True, pull_thresh=32, push_thresh=32, out_shiftdir=rp2.PIO.SHIFT_RIGHT, in_shiftdir=rp2.PIO.SHIFT_LEFT)
def debug():
    out(x, 32)
    in_(x, 32)


BACK_PORCH_START = VERT_SYNC * VSYNC_LINE_LENGTH
IMAGE_START = BACK_PORCH_START + VERT_BACK_PORCH * PORCH_LINE_LENGTH
FRONT_PORCH_START = IMAGE_START + VERT_IMAGE * IMAGE_LINE_LENGTH
TOTAL_LENGTH = FRONT_PORCH_START + VERT_FRONT_PORCH * PORCH_LINE_LENGTH


# disables and aborts all DMA channels, does not reset confifguration
# micropython does not reset DMA by itself
def reset_dma():
    # disable DMA channels
    machine.mem32[DMA_CH0 + DMA_CTRL] &= ~1
    machine.mem32[DMA_CH1 + DMA_CTRL] &= ~1

    # abort DMA channels
    machine.mem32[DMA_CHANNEL_BASE + DMA_ABORT] = 0x0000ffff

    while machine.mem32[DMA_CHANNEL_BASE + DMA_ABORT] != 0:
        pass


# channel 0 reads the start address of the array from constants[1]
# and writes it to the READ_ADDR_TRIG register of channel 1
# this starts channel 1 without chaining

# channel 1 reads the data from the array and writes it to the TX FIFO of PIO0
# it chains back to channel 0

def setup_dma(arr):
    constants[0] = uctypes.addressof(arr)

    machine.mem32[DMA_CH0 + DMA_READ_ADDR] = DMA_READ_TARGET_ADDR
    machine.mem32[DMA_CH0 + DMA_WRITE_ADDR] = DMA_CH1 + DMA_READ_TRIG
    machine.mem32[DMA_CH0 + DMA_TRANS_COUNT] = 1
    ctrl = 0
    ctrl |= 1 # enable
    ctrl |= 1 << 3 # 4 byte transfers
    ctrl |= 0x3f << 15 # unlimited speed

    machine.mem32[DMA_CH1 + DMA_WRITE_ADDR] = PIO0_TXF0
    machine.mem32[DMA_CH1 + DMA_TRANS_COUNT] = TOTAL_LENGTH // 4 # 4 bytes per transfer

    ctrl2 = 0
    ctrl2 |= 1 # enable
    ctrl2 |= 1 << 3 # 4 byte transfers
    ctrl2 |= 1 << 4 # increment source address
    ctrl2 |= 0x00 << 11 # chain to channel 0
    ctrl2 |= DREQ_PIO0_TX0 <<  15 # trigger on PIO0 TX FIFO

    machine.mem32[DMA_CH1 + DMA_CTRL] = ctrl2
    machine.mem32[DMA_CH0 + DMA_CTRL_TRIG] = ctrl





    
    


    
def make_array():
    arr = bytearray(VERT_SYNC * VSYNC_LINE_LENGTH + (VERT_FRONT_PORCH + VERT_BACK_PORCH) * PORCH_LINE_LENGTH + VERT_IMAGE * IMAGE_LINE_LENGTH)

    for i in range(VERT_SYNC):
        arr[i * VSYNC_LINE_LENGTH : (i + 1) * VSYNC_LINE_LENGTH] = VSYNC_LINE_BYTES

    for i in range(VERT_BACK_PORCH):
        arr[BACK_PORCH_START + i * PORCH_LINE_LENGTH : BACK_PORCH_START + (i + 1) * PORCH_LINE_LENGTH] = PORCH_LINE_BYTES

    for i in range(VERT_IMAGE):
        arr[IMAGE_START + i * IMAGE_LINE_LENGTH : IMAGE_START + (i + 1) * IMAGE_LINE_LENGTH] = IMAGE_LINE_BYTES_PREFIX + bytearray(640 * BIT_DEPTH // 8)

    for i in range(VERT_FRONT_PORCH):
        arr[FRONT_PORCH_START + i * PORCH_LINE_LENGTH : FRONT_PORCH_START + (i + 1) * PORCH_LINE_LENGTH] = PORCH_LINE_BYTES

    return arr






reset_dma()


sm = rp2.StateMachine(0, write_colour, freq=FREQUENCY, out_base=Pin(0), set_base=Pin(14))
sm.active(1)

arr = make_array()
view = memoryview(arr)

image_area = view[IMAGE_START + IMAGE_LINE_PREFIX_LENGTH : FRONT_PORCH_START]

frame = framebuf.FrameBuffer(image_area, 640, 480, framebuf.MONO_HMSB, (IMAGE_LINE_PREFIX_LENGTH * 8 // BIT_DEPTH) + 640)

frame.fill(1)

setup_dma(arr)

frame.text("Hello World!", 100, 100, 0)

for i in range(1000000):
    frame.rect(100, 200, 50, 10, 1, 1)
    frame.text(str(i), 100, 200, 0)
    time.sleep_ms(10)