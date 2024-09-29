# autopunkconsole code.py -- Do Atari Punk Console-like sound, but automatically
#                            for the MacroPad RP2040 with MacroPadSynthPlug or built-in speaker
#
# 1 Mar 2023 - @todbot / Tod Kurt
#
# `cedargrove_punkconsole` can be found at https://github.com/CedarGroveStudios/CircuitPython_PunkConsole
# or installing with circup: `circup install cedargrove_punkconsole`
#
# DANGER: this makes really annoying noises
#

import time
import board, busio, keypad, rotaryio, digitalio
import displayio, terminalio
import rainbowio

import noise
import neopixel
from simpleio import map_range
from adafruit_display_text.bitmap_label import Label
from cedargrove_punkconsole import PunkConsole

use_macropadsynthplug = False

punk_pin = board.SDA    # macropadsynthplug!
if not use_macropadsynthplug: # or, built-in speaker!
    punk_pin = board.SPEAKER # built-in tiny spkr
    speaker_en = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
    speaker_en.switch_to_output(value=True)

punk_console = PunkConsole(punk_pin, mute=False)

leds = neopixel.NeoPixel(board.NEOPIXEL, 12, brightness=0.2, auto_write=False)
leds.fill(0xff00ff); leds.show()
key_pins = (board.KEY1, board.KEY2, board.KEY3,
            board.KEY4, board.KEY5, board.KEY6,
            board.KEY7, board.KEY8, board.KEY9,
            board.KEY10, board.KEY11, board.KEY12)
keys = keypad.Keys(key_pins, value_when_pressed=False, pull=True)
encoder = rotaryio.IncrementalEncoder(board.ENCODER_B, board.ENCODER_A)  # yes, reversed
encoder_switch = keypad.Keys((board.ENCODER_SWITCH,), value_when_pressed=False, pull=True)
# keys & encoders not used yet

# display setup
display = board.DISPLAY
display.rotation = 0
font = terminalio.FONT
mainscreen = displayio.Group()
display.root_group = mainscreen
mainscreen.append( Label(font, text="macropad",          x=0,  y=15) )
mainscreen.append( Label(font, text="autopunkconsole",   x=0,  y=30) )
mainscreen.append( Label(font, text="freq:",             x=0,  y=50) )
mainscreen.append( freqlabel := Label(font, text="0000", x=30, y=50) )
mainscreen.append( Label(font, text="pw:",               x=70, y=50) )
mainscreen.append( pwlabel := Label(font, text="00.0",   x=90, y=50) )

t = 0  # our position in noise space
last_display_update = time.monotonic() # only update the display occasionally, since it slows us down

while True:
    n1 = noise.noise(t)  # get value of noise at t
    n2 = noise.noise(t/2)  # and at t/2 (moves slower through noise space)
    t += 0.003  # move a little bit in noise space

    # map noise to appropriate values for punk_console
    # Oscillator Frequency, 3 - 3000 Hz
    # One-Shot Pulse Width, 0.5 - 5.0 ms
    punk_console.frequency = map_range( n1, -1,1, 3, 2000)
    punk_console.pulse_width_ms  = map_range( n2, -1,1, 0.5, 5.0)

    # compute which LED to light up, and its hue
    p = int(  n1 * 100 ) % 12
    leds[ p ] = rainbowio.colorwheel( n1 * 10000)
    leds.show()

    # update display
    if time.monotonic() - last_display_update > 0.1:
        last_display_update = time.monotonic()
        freqlabel.text = "%4d" % f_in
        pwlabel.text = "%2.1f" % pw_in
