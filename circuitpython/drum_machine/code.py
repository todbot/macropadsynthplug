# macropadsynthplug drum machine code.py - play multiple samples concurrently, some looped, some not
#
# 5 Feb 2022 - @todbot / Tod Kurt - https://github.com/todbot/macropadsynthplug
#
# Copy this file as "code.py" to your CIRCUITPY drive
# Install "neopixel" library with "circup install neopixel"
#
# Convert files to appropriate WAV format (mono, 22050 Hz, 16-bit signed) with command:
#  sox loop.mp3 -b 16 -c 1 -r 22050 loop.wav
# or try:
#  ffmpeg -i loop.mp3 -ac 1 -ar 22050 loop.wav  (but I think this needs codec spec'd
#

print("macropadsynthplug drum machine!")

import time
import supervisor
import board, busio, keypad, rotaryio
import displayio, terminalio
import rainbowio
import audiocore, audiomixer, audiopwmio
import neopixel
from adafruit_display_text import bitmap_label as label
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff


# map key number to wave file
# a list of which samples to play on which keys,
# and if the sample should loop or not
# if a key has no sample, use (None,None)
wav_files = (
    # filename,           loop?
    ('wav/909kick4.wav', False),        # 0
    ('wav/909clap1.wav', False),        # 1
    ('wav/909snare2.wav', False),       # 2
    ('wav/909cym2.wav', False),         # 3
    ('wav/909hatclosed2.wav', False),   # 4
    ('wav/909hatopen5.wav', False),     # 5
    ('wav/dnb21580_22k16b_160bpm.wav', True),  # 6
    ('wav/drumloopA_22k16b_160bpm.wav',True),  # 7
    ('wav/909cym2.wav', False),      # 8
    ('wav/ohohoh_22k16b_160bpm.wav', True),    # 9
    ('wav/secretguit_22k16b_160bpm.wav',True), # 10
    ('wav/guit1403_22k16b_160bpm.wav', True),  # 11
)

# macropadsynthplug!
midi_uart = busio.UART(rx=board.SCL, tx=None, baudrate=31250, timeout=0.001)
#midi_uart_in = smolmidi.MidiIn(midi_uart)
midi_uart_in = adafruit_midi.MIDI( midi_in=midi_uart) # , debug=False)
midi_usb_in = adafruit_midi.MIDI( midi_in=usb_midi.ports[0])

leds = neopixel.NeoPixel(board.NEOPIXEL, 12, brightness=0.3, auto_write=False)

key_pins = (board.KEY1, board.KEY2, board.KEY3,
            board.KEY4, board.KEY5, board.KEY6,
            board.KEY7, board.KEY8, board.KEY9,
            board.KEY10, board.KEY11, board.KEY12)

keys = keypad.Keys(key_pins, value_when_pressed=False, pull=True)
encoder = rotaryio.IncrementalEncoder(board.ENCODER_B, board.ENCODER_A)  # yes, reversed
encoder_switch = keypad.Keys((board.ENCODER_SWITCH,), value_when_pressed=False, pull=True)

num_voices = len(wav_files)
audio = audiopwmio.PWMAudioOut(board.SDA) # macropadsynthplug!
mixer = audiomixer.Mixer(voice_count=num_voices, sample_rate=22050, channel_count=1,
                         bits_per_sample=16, samples_signed=True, buffer_size=2048)
audio.play(mixer) # attach mixer to audio playback


# display setup begin
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT
dispgroup = displayio.Group()
display.show(dispgroup)
text1 = label.Label(font, text="macropad", x=0, y=10)
text2 = label.Label(font, text="synthplug", x=0, y=20)
text3 = label.Label(font, text="drumachine", x=0, y=30)
text_rcv = label.Label(font, text="recv:", x=0, y=60)
text_rcv_val = label.Label(font, text="   ", x=10, y=70)
dispgroup.append( text1 )
dispgroup.append( text2 )
dispgroup.append( text3 )
dispgroup.append( text_rcv )
dispgroup.append( text_rcv_val )
# display setup end

# play or stop a sample using the mixer
def handle_sample(num, pressed):
    voice = mixer.voice[num]   # get mixer voice
    (wav_file, loopit) = wav_files[num]
    if pressed:
        if wav_file is not None:
            wave = audiocore.WaveFile(open(wav_file,"rb"))
            voice.play(wave,loop=loopit)
    else: # released
        if loopit:
            voice.stop()  # only stop looping samples, others one-shot

def midi_receive():
    while msg := midi_uart_in.receive() or midi_usb_in.receive():
        if msg is not None:
            print(time.monotonic(), msg)
            if isinstance(msg, NoteOn) and msg.velocity:
                print("noteOn:",msg.note, msg.note % 12)
                handle_sample( msg.note % 12, True)
            if isinstance(msg,NoteOff) or (isinstance(msg, NoteOn) and msg.velocity==0):
                handle_sample( msg.note % 12, False)

def millis(): return supervisor.ticks_ms()  # I like millis

# scale a value by amount/256, expects an int, returns an int
def scale8(val,amount):
    return (val*amount)//256

# dim all leds by an (amount/256)
def dim_leds_by(leds, amount):
    leds[:] = [[max(scale8(i,amount),0) for i in l] for l in leds]

#leds.fill(0x333333)

led_last_update_millis = 0
led_millis = 5

keys_pressed = [False] * num_voices  # list of keys currently being pressed down
while True:

    midi_receive()

    now = millis()
    # update the LEDs, but only if keys pressed
    if now - led_last_update_millis > led_millis:
        led_last_update_millis = now
        for i in range(num_voices):  # light up those keys that are pressed
            if keys_pressed[i]:
                leds[ i ] = rainbowio.colorwheel( int(time.monotonic() * 20) )
        dim_leds_by(leds, 250)  # fade everyone out slowly
        leds.show()


    # Key handling
    key = keys.events.get()
    if key:
        print("key:%d %d/%d %d" % (key.key_number, key.pressed, key.released, key.timestamp) )

        if key.pressed:
            handle_sample( key.key_number, True )
            keys_pressed[ key.key_number ] = True

        if key.released:
            handle_sample( key.key_number, False )
            keys_pressed[ key.key_number ] = False
