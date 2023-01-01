# macropadsynthplug_drum_machine_code.py - drum machine on MacroPad RP2040
#
# 28 Dec 2022 - @todbot / Tod Kurt - https://github.com/todbot/macropadsynthplug
#
# Rotate macropad so keys are to the right, knob is top left
# - Key next to macropad is PLAY/STOP,
# - Then RECORD key
# - Then MUTE key
# - Then TEMPO key
# - The bottom two rows of 4 keys are the drum triggers
# - Push encoder to switch between pattern changing mode & BPM changing mode
#
#  +-------+------+------+------+------+
#  |  ---  |      |      |      |      |
#  | | O | | Play | Rec  | Mute | Tap  |
#  |  ---  |      |      |      |      |
#  | ----- +------+------+------+------+
#  | |   | |      |      |      |      |
#  | |   | |  4   |  5   |  6   |  7   |
#  | |   | |      |      |      |      |
#  | |   | +------+------+------+------+
#  | |   | |      |      |      |      |
#  | |   | |  0   |  1   |  2   |  3   |
#  | ----- |      |      |      |      |
#  |-------+------+------+------+------+
#
#
# To install:
# - Copy this file and this whole directory to your CIRCUITPY drive
# - Install other libraries with "circup install neopixel adafruit_display_text adafruit_midi"
#
# Convert drum sounds to appropriate WAV format (mono, 22050 Hz, 16-bit signed) with command:
#  sox sound.mp3 -b 16 -c 1 -r 22050 sound.wav
#

print("macropadsynthplug drum machine start!")

import time
import supervisor
import board, busio, keypad, rotaryio, digitalio
import displayio, terminalio
import rainbowio
import audiocore, audiomixer, audiopwmio
import neopixel
from adafruit_display_text import bitmap_label as label
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

from drum_patterns import *

use_macrosynthplug = True
debug = True

patt_index = 0  # which sequence we're playing from our list of avail patterns
bpm = 120  # default BPM
steps_per_beat = 8  # divisions per beat: 8 = 32nd notes, 4 = 16th notes
num_pads = 8

sequence = make_sequence( patterns[patt_index] )
num_steps = len(sequence)  # number of steps

# map key number to wave file
# a list of which samples to play on which keys,
# and if the sample should loop or not
# if a key has no sample, use (None,None)
wav_files = (
    # filename,           loop?
    ('wav/909kick4.wav', False),        # 0  # |....|x...|
    ('wav/909clap1.wav', False),        # 1  # |....|.x..|
    ('wav/909snare2.wav', False),       # 2  # |....|..x.|
    ('wav/909cym2.wav', False),         # 3
    ('wav/909hatclosed2a.wav', False),  # 4
    ('wav/909hatopen5.wav', False),     # 5
    ('wav/laser2.wav', False),  # 6
    ('wav/laser2.wav',False),  # 7
)

# top row of keys is special
key_PLAY = 2
key_RECORD= 5
key_MUTE = 8
key_TAP_TEMPO = 11
# the rest of keys are drum pads
keynum_to_padnum = (0, 4, -1, # pad nums go from bottom row of four: 0,1,2,3
                    1, 5, -1, # then above that, next row of four 4,5,6,7
                    2, 6, -1, # and top row are invalid pad nums (buttons used for transport)
                    3, 7, -1)

# macropadsynthplug!
midi_uart = busio.UART(rx=board.SCL, tx=None, baudrate=31250, timeout=0.001)
#midi_uart_in = smolmidi.MidiIn(midi_uart) # can't do smolmidi because it wants port.readinto(buf,len)
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

if use_macrosynthplug:
    audio = audiopwmio.PWMAudioOut(board.SDA) # macropadsynthplug!
else:
    audio = audiopwmio.PWMAudioOut(board.SPEAKER) # built-in tiny spkr
    speaker_en = digitalio.DigitalInOut(board.SPEAKER_ENABLE)
    speaker_en.switch_to_output(value=True)
mixer = audiomixer.Mixer(voice_count=num_pads, sample_rate=22050, channel_count=1,
                         bits_per_sample=16, samples_signed=True, buffer_size=2048)
audio.play(mixer) # attach mixer to audio playback


# display setup begin
dw,dh = 64,128
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT
dispgroup = displayio.Group()
display.show(dispgroup)
txt1 = label.Label(font, text="macropad",      x=0,  y=10)
txt2 = label.Label(font, text="synthplug",     x=0,  y=20)
txt3 = label.Label(font, text="drumachine",    x=0,  y=30)

#txt_mode = label.Label(font, text="n:",      x=0,  y=45)
txt_mode_val = label.Label(font, text="stop",  x=40, y=45)

txt_emode1 = label.Label(font,text=">",        x=0,  y=60)
txt_patt = label.Label(font, text="patt",      x=8,  y=60)
txt_emode0 = label.Label(font,text=" ",        x=0,  y=75)
txt_bpm = label.Label(font, text="bpm:",       x=8,  y=75)
txt_bpm_val = label.Label(font, text=str(bpm), x=35, y=75)
txt_rcv = label.Label(font, text="midi:",      x=0, y=115)
txt_rcv_val = label.Label(font, text="   ",    x=10, y=120)
for t in (txt1, txt2, txt3, txt_emode1, txt_emode0, txt_patt,
          txt_mode_val, txt_bpm, txt_bpm_val, txt_rcv, txt_rcv_val):
    dispgroup.append(t)
# display setup end

def millis(): return supervisor.ticks_ms()  # I like millis


# sequence state
steps_millis = 0 # derived from bpm, changed by "update_bpm()" below
last_step_millis = millis()
seq_pos = 0  # where in our sequence we are
playing = False
recording = False

# UI state
pads_lit = [0] * num_pads  # list of drum keys that are being played
pads_mute = [0] * num_pads # which pads are muted
last_led_millis = 0
led_millis = 5  # how often to update the LEDs
rec_pressed = False  # for deleting tracks
mute_pressed = False  # for muting/unmuting tracks
encoder_val_last = encoder.position
encoder_mode = 1  # 0 = change bpm, 1 = change pattern

# Load wave objects upfront to reduce play latency
waves = [None] * num_pads
for i in range(num_pads):
    waves[i] = audiocore.WaveFile(open(wav_files[i][0],"rb"))  # ignore 'loopit'

# Play or stop a sample using the mixer
def handle_sample(num, pressed):
    pads_lit[num] = pressed
    voice = mixer.voice[num]   # get mixer voice
    if pressed and not pads_mute[num]:
        voice.play(waves[num],loop=False)
    else: # released
        pass
        #if loopit:
        #voice.stop()  # only stop looping samples, others one-shot

# Get midi from UART or USB
def midi_receive():
    while msg := midi_uart_in.receive() or midi_usb_in.receive():  # walrus!
        if msg is not None:
            print(time.monotonic(), msg)
            if isinstance(msg, NoteOn) and msg.velocity:
                print("noteOn:",msg.note, msg.note % 12)
                handle_sample( msg.note % 12, True)
            if isinstance(msg,NoteOff) or (isinstance(msg, NoteOn) and msg.velocity==0):
                handle_sample( msg.note % 12, False)

def update_play():
    if playing:
        txt_mode_val.text = "play" if not recording else "odub"
    else:
        txt_mode_val.text = "stop" if not recording else "reco"  # FIXME:

def update_bpm():
    global steps_millis
    # Beat timing assumes 4/4 time signature, e.g. 4 beats per measure, 1/4 note gets the beat
    beat_time = 60 / bpm  # time length of a single beat
    beat_millis = beat_time * 1000  # time length of single beat in milliseconds
    steps_millis = int(beat_millis / steps_per_beat)  # time length of a beat subdivision, e.g. 1/16th note
    txt_bpm_val.text = str(bpm)
    # and keep "steps_millis" an int so diff math is fast

def update_pattern():
    txt_patt.text = patterns[patt_index]['name']

def update_encmode():
    if encoder_mode == 0:
        txt_emode0.text = '>'
        txt_emode1.text = ' '
    elif encoder_mode == 1:
        txt_emode0.text = ' '
        txt_emode1.text = '>'


# for debugging
def print_sequence():
    print("    {")
    print("        'name':'dump'")
    print("        'len':", len(sequence))
    print("        'base': [")
    for i in range(len(sequence)):
        print("            [" + ",".join('1' if e else '0' for e in sequence[i]) + "],")
    print("        ]");
    print("    }")

update_play()
update_pattern()
update_bpm()


print("macropadsynthplug drum machine ready!  bpm:", bpm, "steps_millis:", steps_millis, "steps:", num_steps)

while True:

    # midi_receive()

    now = millis()

    # LED handling
    if now - last_led_millis > led_millis:
        last_led_millis = now
        leds[key_PLAY]   = 0x00FF00 if playing else 0x114400
        leds[key_RECORD] = 0xFF0000 if recording else 0x440044 if rec_pressed else 0x441100
        leds[key_MUTE]   = 0x001144  # mute mode button
        for i in range(num_pads):  # light up pressed drumpads
            if mute_pressed:  # show mute state instead
                leds[ keynum_to_padnum.index(i) ] = 0x000000 if pads_mute[i] else 0x001144
            if pads_lit[i]:
                leds[ keynum_to_padnum.index(i) ] = rainbowio.colorwheel( int(time.monotonic() * 20) )
        leds[:] = [[max(i-5,0) for i in l] for l in leds] # fade released drumpads slowly
        leds.show()

    fudge = 2

    # Sequencer playing
    diff = now - last_step_millis
    if diff > steps_millis:
        late_millis = diff - steps_millis # how much are we over
        last_step_millis = now - (late_millis//2) - fudge

        # tempo indicator
        if seq_pos % steps_per_beat == 0: leds[key_TAP_TEMPO] = 0x333333
        if seq_pos == 0: leds[key_TAP_TEMPO] = 0x3333FF # first beat indicator

        if playing:
            # play any sounds previously recorded for this step
            for i in range(num_pads):
                handle_sample(i, sequence[seq_pos][i] )

            if(debug): print("%2d %3d" % (late_millis, seq_pos), sequence[seq_pos])

        seq_pos = (seq_pos + 1) % num_steps # FIXME: let user choose?

    # Key handling
    key = keys.events.get()
    if key:
        keynum = key.key_number
        # print("key:%d %d" % (keynum, key.pressed) )

        if keynum == key_PLAY:
            if key.pressed:
                playing = not playing
                if recording and playing:
                    pass  # maybe erasing sequence?
                if playing:
                    last_playing_millis = now - steps_millis
                    seq_pos = 0
                else:  # we are stopped
                    recording = False # so turn off recording too
                    print_sequence()  # "saving" it
                update_play()

        elif keynum == key_RECORD:
            rec_pressed = key.pressed
            if rec_pressed:
                recording = not recording # toggle record state
                update_play()

        elif keynum == key_MUTE:
            mute_pressed = key.pressed

        elif keynum == key_TAP_TEMPO:
            pass

        else: # else its a drumpad, either trigger, erase track, or mute track
            padnum = keynum_to_padnum[keynum]
            # print("keynum:", keynum, "padnum:",padnum)
            if key.pressed:
                # if REC button held while pad press, erase track
                if rec_pressed:
                    for i in range(num_steps):
                        sequence[i][padnum] = 0
                # if MUTE button held, mute/unmute track
                elif mute_pressed:
                    pads_mute[padnum] = not pads_mute[padnum]
                # else trigger drum
                else:
                    if recording:
                        sequence[ seq_pos ][padnum] = 1
                    else:
                        handle_sample( padnum, 1 )

                    # and start recording on the beat if set to record
                    if recording and not playing:
                        playing = True
                        last_playing_millis = millis() - steps_millis
                        seq_pos = 0

            if key.released:
                handle_sample( padnum, 0 )

    # Encoder push handling
    enc_sw = encoder_switch.events.get()
    if enc_sw:
        if enc_sw.pressed:
            encoder_mode = (encoder_mode + 1) % 2
            update_encmode()

    # Encoder turn handling
    encoder_val = encoder.position
    if encoder_val != encoder_val_last:
        encoder_delta = (encoder_val - encoder_val_last)
        encoder_val_last = encoder_val
        if encoder_mode == 0:
            bpm += encoder_delta
            update_bpm()
        elif encoder_mode == 1:
            patt_index = (patt_index + encoder_delta) % len(patterns)
            print("pattern:", patt_index)
            sequence = make_sequence(patterns[patt_index])
            update_pattern()
