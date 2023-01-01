# macropadsynthplug_remixer.py -- song remixer
# 20 Dec 2022 - @todbot / Tod Kurt
#
# Remix an existing sample using macropad
#

import time
import board, busio, keypad, rotaryio, neopixel
import displayio, terminalio
import usb_midi
import audiocore, audiomixer, audiopwmio
from adafruit_display_text import bitmap_label as label
#from adafruit_ticks import ticks_ms, ticks_diff, ticks_add
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff
#import winterbloom_smolmidi as smolmidi  # cannot use this yet, depends on port.readinto(val,len)

# map key number to wave file
# a list of which samples to play on which keys,
# and if the sample should loop or not
# if a key has no sample, use (None,None)
wav_files = (
    # filename,           loop?
    ('wav/pmpsp1F3.wav',    True), # 0 key
    ('wav/pmpsp2C2.wav',    True), # 1
    ('wav/pmpsp3C1.wav',    True), # 2
    ('wav/pmpsp4drum.wav',  True), # 3
    ('wav/pmpsp5G3.wav',    True), # 4
    ('wav/pmpsp6C3.wav',    True), # 5
    ('wav/pmpsp7Ds3.wav',   True), # 6
    ('wav/pmpsp4drum2.wav', True), # 7
    ('wav/pmpsp4drum2.wav', True), # 8
    ('wav/pmpsp4drum2.wav', True), # 9
    ('wav/pmpsp4drum2.wav', True), # 10
    ('wav/pmpsp12clap.wav', True), # 11
)

# macropadsynthplug!
midi_uart = busio.UART(rx=board.SCL, tx=None, baudrate=31250, timeout=0.001)
#midi_uart_in = smolmidi.MidiIn(midi_uart)
midi_uart_in = adafruit_midi.MIDI( midi_in=midi_uart, debug=False)

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

vol_max = 0.48

# display setup begin
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT
dispgroup = displayio.Group()
display.show(dispgroup)
text1 = label.Label(font, text="macropad", x=0,  y=10)
text2 = label.Label(font, text="synthplug", x=0,  y=20)
text_rcv = label.Label(font, text="recv:", x=0,  y=60)
text_rcv_val = label.Label(font, text="   ", x=10,  y=70)
dispgroup.append( text1 )
dispgroup.append( text2 )
dispgroup.append( text_rcv )
dispgroup.append( text_rcv_val )
# display setup end

waves = [None] * num_voices
for i in range(num_voices):
    wav_file,loop = wav_files[i]
    wave = audiocore.WaveFile(open(wav_file,"rb"))
    waves[i] = wave

for i in range(num_voices):
    voice = mixer.voice[i]
    voice.level = 0
    #wav_file,loop = wav_files[i]
    #wave = audiocore.WaveFile(open(wav_file,"rb"))
    voice.play(waves[i], loop=True)

keys_pressed = [False] * num_voices
last_key_time = time.monotonic()

def trigger_note(kind,note,vel):
    n = note % 12
    keys_pressed[n] = True if vel > 0 else False
    text_rcv_val.text = f"{kind} {note} {vel}"

def midi_receive():
    msg = midi_uart_in.receive()
    if msg is not None:
        print(time.monotonic(), msg)
        if isinstance(msg, NoteOn) and msg.velocity:
            print("noteOn:",msg.note, msg.note % 12)
            trigger_note('m', msg.note,msg.velocity)
        if isinstance(msg,NoteOff) or (isinstance(msg, NoteOn) and msg.velocity==0):
            trigger_note('m', msg.note,0)

encoder_val_last = encoder.position


print("macropadsynthplug_hw_test!")
while True:

    midi_receive()

    # adjust volume based on pressed/released keys
    if time.monotonic() - last_key_time > 0.05:
        last_key_time = time.monotonic()
        for i in range(num_voices):
            k = keys_pressed[i]
            vinc = -0.01 # how fast volume should go up/down
            if k: vinc = -vinc
            voice = mixer.voice[i]
            voice.level = min(max(voice.level + vinc, 0), vol_max) # constrain 0-vol_max
            leds[i] = (voice.level * 255, 0, voice.level * 255)
        #     print("%0.1f " % voice.level, end='')
        # print()
        leds.show()

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

    # only pressed / released key logic beyond this point

    # otherwise key was pressed or released
    keynum = key.key_number
    print("key!",keynum, key.pressed)

    if key.pressed:
        trigger_note('k', keynum, 127)

    if key.released:
        trigger_note('k', keynum, 0)
