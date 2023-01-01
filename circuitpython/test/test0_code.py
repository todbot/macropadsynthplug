import time
import board, busio, keypad, rotaryio, neopixel
import displayio, terminalio
import usb_midi
from adafruit_display_text import bitmap_label as label
from adafruit_ticks import ticks_ms, ticks_diff, ticks_add
import adafruit_midi

midi_uart = busio.UART(rx=board.SCL, tx=None, baudrate=31250, timeout=0.01)

leds = neopixel.NeoPixel(board.NEOPIXEL, 12, brightness=0.2, auto_write=False)

key_pins = (board.KEY1, board.KEY2, board.KEY3,
            board.KEY4, board.KEY5, board.KEY6,
            board.KEY7, board.KEY8, board.KEY9,
            board.KEY10, board.KEY11, board.KEY12)

keys = keypad.Keys(key_pins, value_when_pressed=False, pull=True)
encoder = rotaryio.IncrementalEncoder(board.ENCODER_B, board.ENCODER_A)  # yes, reversed
encoder_switch = keypad.Keys((board.ENCODER_SWITCH,), value_when_pressed=False, pull=True)

# display setup begin
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT
dispgroup = displayio.Group()
display.show(dispgroup)
bpm_text  = label.Label(font, text="bpm:", x=0,  y=10)
bpm_val   = label.Label(font, text="xxx",  x=24, y=10)
drum_text = label.Label(font, text="drum:", x=0,  y=20)
drum_val  = label.Label(font, text="xxxx", x=32, y=20)
dispgroup.append( bpm_text )
dispgroup.append( bpm_val )
dispgroup.append( drum_text )
dispgroup.append( drum_val )
# display setup end

midi_uart_in = adafruit_midi.MIDI( midi_in=midi_uart, debug=True)

def midi_receive():
    msg = midi_uart_in.receive()
    if msg is not None:
        print(time.monotonic(), msg)


encoder_val_last = encoder.position

while True:

    midi_receive()

    # Encoder turning
    encoder_val = encoder.position
    if encoder_val != encoder_val_last:
        encoder_delta = (encoder_val - encoder_val_last)
        encoder_val_last = encoder_val
        print("encoder!", encoder_delta)

    # Encoder push
    encsw = encoder_switch.events.get()
    if encsw:
        if encsw.pressed:
            print("encoder press!")
        if encsw.released:
            pass  # nothing yet

    # Key handling
    key = keys.events.get()
    if key == None:
        continue   # no keys? go back to while

    # otherwise key was pressed or released
    keynum = key.key_number
    print("key!",key)

    # if keynum == 2:  # play / stop
    #     if key.pressed:
    #         pass
    #     if key.released:
    #         pass  # nothing yet
    # elif keynum == 5:
    #     if key.pressed:
    #         pass
    # elif keynum == 8:
    #     if key.pressed:
    #         pass
    # elif keynum == 11:
    #     if key.pressed:
    #         pass
    # else: # step key
    #     step_push = step_to_key_pos.index(keynum)
    #     val = sequence[state.curr_drum][step_push]
    #     if key.pressed:
    #         sequence[state.curr_drum][step_push] = not val
