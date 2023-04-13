from machine import Pin
import time
import micropython
import rp2
from micropython import const
import array
import uctypes
import machine
import framebuf

machine.freq(130000000)

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

constants = array.array("L", [
    0x10101100, # pattern to write to PIO0_OUT
])


signals = array.array("L", [
    0x01010101,
    0x00001111,
    0x00110011,
    0x01110111
])


def reset_dma():
    machine.mem32[DMA_CH0 + DMA_CTRL] &= ~1
    machine.mem32[DMA_CH1 + DMA_CTRL] &= ~1


    machine.mem32[DMA_CHANNEL_BASE + DMA_ABORT] = 0x0000ffff

    while machine.mem32[DMA_CHANNEL_BASE + DMA_ABORT] != 0:
        pass

def setup_dma(arr):
    constants[0] = uctypes.addressof(arr)

    machine.mem32[DMA_CH0 + DMA_READ_ADDR] = uctypes.addressof(constants)
    machine.mem32[DMA_CH0 + DMA_WRITE_ADDR] = DMA_CH1 + DMA_READ_TRIG
    machine.mem32[DMA_CH0 + DMA_TRANS_COUNT] = 1
    ctrl = 0
    ctrl |= 1 # enable
    ctrl |= 1 << 3 # 4 byte transfers
    ctrl |= 0x3f << 15 # unlimited speed

    machine.mem32[DMA_CH1 + DMA_WRITE_ADDR] = PIO0_TXF0
    machine.mem32[DMA_CH1 + DMA_TRANS_COUNT] = 4

    ctrl2 = 0
    ctrl2 |= 1 # enable
    ctrl2 |= 1 << 3 # 4 byte transfers
    ctrl2 |= 1 << 4 # increment source address
    ctrl2 |= 0x00 << 11 # chain to channel 0
    ctrl2 |= DREQ_PIO0_TX0 <<  15 # trigger on PIO0 TX FIFO

    machine.mem32[DMA_CH1 + DMA_CTRL] = ctrl2
    machine.mem32[DMA_CH0 + DMA_CTRL_TRIG] = ctrl





@rp2.asm_pio(out_init=rp2.PIO.OUT_LOW, autopull=True, pull_thresh=32, out_shiftdir=rp2.PIO.SHIFT_RIGHT)
def write_pixels():
    out(pins, 1)
    out(y, 3)
    set(x, 31)
    label("loop")
    jmp(x_dec, "loop") [15]

reset_dma()

sm = rp2.StateMachine(0, write_pixels, freq=2000, out_base=Pin(25))
sm.active(1)

setup_dma(signals)

#sm.put(constants[0])