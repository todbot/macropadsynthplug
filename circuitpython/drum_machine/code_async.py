# macropadsynthplug_drum_machine_async_code.py - drum machine on MacroPad RP2040
#
# 28 Dec 2022 - @todbot / Tod Kurt - https://github.com/todbot/macropadsynthplug
#
# Rotate macropad so keys are to the right, knob is top left
# - Key next to macropad is PLAY/STOP,
# - Then RECORD key
# - Then MUTE key (unimplemented)
# - Then TEMPO key
# - The bottom two rows of 4 keys are the drum triggers
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

print("macropadsynthplug drum machine async start!")

import asyncio
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

from drum_patterns import *

bpm = 120  # default BPM
steps_per_beat = 8  # divisions per beat: 8 = 32nd notes, 4 = 16th notes
num_pads = 8
patt_index = 0  # which sequence we're playing from our list of avail patterns

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
key_MODE = 8
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

audio = audiopwmio.PWMAudioOut(board.SDA) # macropadsynthplug!
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
txt_patt = label.Label(font, text="patt",      x=0,  y=45)
txt_mode = label.Label(font, text="mode:",     x=0,  y=60)
txt_mode_val = label.Label(font, text="stop",  x=30, y=60)
txt_bpm = label.Label(font, text="bpm:",       x=0,  y=70)
txt_bpm_val = label.Label(font, text=str(bpm), x=30, y=70)
txt_rcv = label.Label(font, text="recv:",      x=0, y=110)
txt_rcv_val = label.Label(font, text="   ",    x=10, y=120)
for t in (txt1, txt2, txt3, txt_patt, txt_mode, txt_mode_val, txt_bpm,
          txt_bpm_val, txt_rcv, txt_rcv_val):
    dispgroup.append(t)
# display setup end

def millis(): return supervisor.ticks_ms()  # I like millis


# sequence state
last_step_millis = millis()  # when our last step was triggered
step_millis = 0 # derived from bpm, changed by "update_bpm()"
seq_pos = 0  # where in our sequence we are
playing = False
recording = False

# UI state
pads_pressed = [0] * num_pads  # list of drum keys currently being pressed down
pads_lit = [0] * num_pads  # list of drum keys that are being played
rec_pressed = False  # is REC button currently pressed, for deleting tracks

# Load wave objects upfront in attempt to reduce play latency
waves = [None] * num_pads
for i in range(num_pads):
    waves[i] = audiocore.WaveFile(open(wav_files[i][0],"rb"))  # ignore 'loopit'

# Play or stop a sample using the mixer
def handle_sample(num, pressed):
    pads_lit[num] = pressed
    voice = mixer.voice[num]   # get mixer voice
    if pressed:
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
    global step_millis
    # Beat timing assumes 4/4 time signature, e.g. 4 beats per measure, 1/4 note gets the beat
    beat_time = 60 / bpm  # time length of a single beat
    beat_millis = beat_time * 1000  # time length of single beat in milliseconds
    step_millis = int(beat_millis / steps_per_beat)  # time length of a beat subdivision, e.g. 1/16th note
    txt_bpm_val.text = str(bpm)
    # and keep "step_millis" an int so diff math is fast

def update_pattern():
    txt_patt.text = patterns[patt_index]['name']

update_play()
update_pattern()
update_bpm()


async def update_leds():
    while True:
        leds[key_PLAY]   = 0x00FF00 if playing else 0x114400
        leds[key_RECORD] = 0xFF0000 if recording else 0x440044 if rec_pressed else 0x441100
        leds[key_MODE]   = 0x001144  # maybe another mode?
        for i in range(num_pads):  # light up pressed drumpads
            if pads_lit[i]:
                leds[ keynum_to_padnum.index(i) ] = rainbowio.colorwheel( int(time.monotonic() * 20) )
        leds[:] = [[max(i-5,0) for i in l] for l in leds] # fade released drumpads slowly
        leds.show()
        await asyncio.sleep(0.01)  # Let another task run.

async def monitor_controls():
    global playing, recording, bpm, rec_pressed, last_playing_millis

    encoder_val_last = encoder.position

    while True:
        await asyncio.sleep(0)  # Let another task run. (at top so we can 'continue')

        # Encoder handling
        encoder_val = encoder.position
        if encoder_val != encoder_val_last:
            encoder_delta = (encoder_val - encoder_val_last)
            encoder_val_last = encoder_val
            bpm += encoder_delta
            update_bpm()

        # Key handling
        key = keys.events.get()
        if key:
            keynum = key.key_number
            # print("key:%d %d" % (keynum, key.pressed) )

            if keynum == key_PLAY:
                if key.pressed:
                    playing = not playing
                    #if recording and playing:
                    #    print("maybe erasing sequence?")
                    if playing:
                        last_playing_millis = millis() - step_millis
                        seq_pos = 0
                    else:  # stopped
                        recording = False # turn off recording too
                    update_play()

            elif keynum == key_RECORD:
                rec_pressed = key.pressed
                if rec_pressed:
                    recording = not recording
                    update_play()

            elif keynum == key_MODE: # dunno what to do wth this key yet
                pass

            elif keynum == key_TAP_TEMPO:
                pass

            else: # else its a drumpad
                padnum = keynum_to_padnum[keynum]
                # print("keynum:", keynum, "padnum:",padnum)
                if key.pressed:
                    if rec_pressed:  # erase sequence
                        for i in range(num_steps):
                            sequence[i][padnum] = 0
                    else: # play drum
                        pads_pressed[padnum] = 1
                        handle_sample( padnum, 1 )

                        # and start recording on the beat if set to record
                        if recording and not playing:
                            playing = True
                            last_playing_millis = millis() - step_millis
                            seq_pos = 0

                if key.released:
                    pads_pressed[padnum] = 0
                    handle_sample( padnum, 0 )

async def run_sequencer():
    global seq_pos, last_step_millis

    while True:
        await asyncio.sleep(0) # run as fast as possible so we can catch lateness

        now = millis()
        diff = now - last_step_millis
        if diff > step_millis:  # sure wish we had a timer facility
            late_millis = diff - step_millis # how much are we late
            last_step_millis = now - (late_millis//2)  #- fudge

            # tempo indicator
            if seq_pos % steps_per_beat == 0: leds[key_TAP_TEMPO] = 0x333333
            if seq_pos == 0: leds[key_TAP_TEMPO] = 0x3333FF # first beat indicator

            if playing:
                # play any sounds previously recorded for this step
                for i in range(num_pads):
                    handle_sample(i, sequence[seq_pos][i] )

                # if recording & pads were pressed,  add it to the _last_ step (the one just finished)
                if recording:
                    for i in range(num_pads):
                        sequence[ seq_pos-1 ][i] |= pads_pressed[i]
                        pads_pressed[i] = 0  # and say we've used it up

                print("%2d %3d" % (late_millis, seq_pos), sequence[seq_pos])

            seq_pos = (seq_pos + 1) % num_steps # go to next step (FIXME: let user choose num_steps?)


# create the tasks that hold our functions
async def main():
    #state = SequencerState()

    leds_task = asyncio.create_task( update_leds() )
    controls_task = asyncio.create_task( monitor_controls() )
    sequencer_task = asyncio.create_task( run_sequencer() )

    await asyncio.gather( leds_task, controls_task, sequencer_task )

# finally start everything running
print("macropadsynthplug drum machine ready!  bpm:", bpm, "step_millis:", step_millis, "steps:", num_steps)
asyncio.run(main())
