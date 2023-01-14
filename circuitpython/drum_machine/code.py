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
#  | .---. |      |      |      |      |
#  | | O | | Play | Rec  | Mute | Tap  |
#  | `---' |      |      |      |      |
#  | ----- +------+------+------+------+
#  | |   | |      |      |      |      |
#  | |   | |  4   |  5   |  6   |  7   |
#  | |   | | clap | tom  | ride | cymb |
#  | |   | +------+------+------+------+
#  | |   | |      |      |      |      |
#  | |   | |  0   |  1   |  2   |  3   |
#  | ----- | kick | snar | hatc | hato |
#  |-------+------+------+------+------+
#
#
# To install:
# - Copy this file and this whole directory to your CIRCUITPY drive
# - Install other libraries with "circup install neopixel adafruit_ticks adafruit_display_text adafruit_midi"
#
# Convert drum sounds to appropriate WAV format (mono, 22050 Hz, 16-bit signed) with command:
#  sox sound.mp3 -b 16 -c 1 -r 22050 sound.wav
#

print("macropadsynthplug drum machine start!")

import time, os, sys, json
import board, busio, keypad, rotaryio, digitalio
import rainbowio
import neopixel
import audiocore, audiomixer, audiopwmio
from adafruit_ticks import ticks_ms, ticks_diff, ticks_add
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

from drum_display import disp_bpm, disp_play, disp_pattern, disp_kit, disp_info, disp_encmode
from drum_patterns import patterns_demo

#time.sleep(3) # wait for USB connect a bit to avoid terible audio glitches

use_macrosynthplug = True  # False to use built-in speaker of MacroPad RP2040
debug = True

patt_index = 0  # which sequence we're playing from our list of avail patterns
bpm = 120  # default BPM
steps_per_beat = 4  # divisions per beat: 8 = 32nd notes, 4 = 16th notes
num_pads = 8  # we use 8 of the 12 macropad keys as drum triggers

#
# MacroPad key layout
#

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

#
# Set up hardware
#

# macropadsynthplug!
midi_uart = busio.UART(rx=board.SCL, tx=None, baudrate=31250, timeout=0.001)
#midi_uart_in = smolmidi.MidiIn(midi_uart) # can't do smolmidi because it wants port.readinto(buf,len)
midi_uart_in = adafruit_midi.MIDI( midi_in=midi_uart) # , debug=False)
midi_usb_in = adafruit_midi.MIDI( midi_in=usb_midi.ports[0])

leds = neopixel.NeoPixel(board.NEOPIXEL, 12, brightness=0.2, auto_write=False)
leds.fill(0xff00ff); leds.show()

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
                         bits_per_sample=16, samples_signed=True, buffer_size=4096)
audio.play(mixer) # attach mixer to audio playback

#
# Sequence management
#

# pattern sequence data structure looks like:
#
# patterns = [
#   { 'name': 'patt0',
#     'seq': [
#             # steps
#             #                       1 1  1 1 1 1
#             # 0 1 2 3  4 5 6 7  8 9 0 1  2 3 4 5  and so on (32)
#             [ 1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0, ... ] # bd
#             [ 0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0, ... ] # sd
#             ... and so on to num_pads (8)
#             ]
#     ]
#  },
# ]
#

# extend a demo pattern that has a 'base' to a full 'seq'
def make_sequence_from_demo_pattern(p):
    sq = []
    # first convert '1010' step strings to 1,0,1,0 numeric array
    for stepline_str in p['base']:
        stepline = [int(c) for c in stepline_str.replace(' ','')]
        sq.append(stepline)
    # then extend 'base' to create 'seq'
    num_copies = p['len'] // len(sq[0])
    sq * num_copies
    return sq

last_write_time = time.monotonic()
def save_patterns():
    global last_write_time
    print("saving patterns...", end='')
    #if ticks_ms() - last_write_time < 10: # only allow writes every 10 seconds, to save flash
    #    print("NO WRITE: TOO SOON")
    #    return
    last_write_time = time.monotonic()
    patts_to_sav = []
    for p in patterns:
        seq_to_sav = [''.join(str(c) for c in l) for l in p['seq']]
        patts_to_sav.append( {'name': p['name'], 'seq': seq_to_sav } )
    with open('/test_saved_patterns.json', 'w') as fp:
    #with sys.stdout as fp:
        json.dump(patts_to_sav, fp)
    print("\ndone")

def load_patterns():
    patts = []
    try:
        with open("/saved_patterns.json",'r') as fp:
            patts = json.load(fp)
            for p in patts:
                # convert str of '1010' to array 1,0,1,0, eliding whitespace, for all seq lines
                p['seq'] = [int(c) for c in s.replace(' ','') for s in p['seq']]
    except (OSError, ValueError) as error:  # maybe no file
        print("load_patterns:",error)

    if len(patts) == 0: # load demo
        print("no saved patterns, loading demo patterns")
        patts = []
        for p in patterns_demo:
            patts.append( {'name':p['name'], 'seq':  make_sequence_from_demo_pattern(p) } )

    return patts  # not strictly needed currently, but wait for it...

def copy_current_pattern():
    global patt_index, sequence
    pname = patterns[patt_index]['name']
    #seq_new = [l.copy() for l in patterns[patt_index]['seq']]  # copy list of lists
    seq_new = [l.copy() for l in sequence]  # copy list of lists
    new_patt = { 'name': 'cptst1',
                 'seq': seq_new }
    patt_index = patt_index + 1
    patterns.insert(patt_index, new_patt)
    sequence = patterns[patt_index]['seq']

def update_step_millis():
    global step_millis
    # Beat timing assumes 4/4 time signature, e.g. 4 beats per measure, 1/4 note gets the beat
    beat_time = 60 / bpm  # time length of a single beat
    beat_millis = beat_time * 1000  # time length of single beat in milliseconds
    step_millis = int(beat_millis / steps_per_beat)  # time length of a beat subdivision, e.g. 1/16th note
    # and keep "step_millis" an int so diff math is fast

#
# Drum kit management
#

# load up the drum kits' info into "kits" data struct
# keys = kit names, values = list of WAV samples
# also special key "kit_names" as order list of kit names
def find_kits():
    kit_root = '/drumkits'
    # Kits should be named/laid out like:
    # 00kick, 01snare, 02hatC, 03hatO, 04clap, 05tomL, 06ride, 07crash,
    # if there aren't 8 smamples
    kits = {}
    for kitname in sorted(os.listdir(kit_root)):
        kname = kitname.lower()
        if not kname.startswith("kit"): # ignore non-kit dirs
            continue
        kits[kname] = []  # holds all sample names of given kit
        for samplename in sorted(os.listdir(f"{kit_root}/{kname}")):
            samplename = samplename.lower()
            if samplename.endswith(".wav") and not samplename.startswith("."):
                kits[kname].append(f"{kit_root}/{kname}/{samplename}") # add it to the bag!
        if len(kits[kname]) < num_pads:
            print(f"ERROR: kit '{kname}' not enough samples! Removing...")
            del kits[kname]
    kits['kit_names'] = sorted(kits.keys())  # add special key of sorted names
    return kits

# Load wave objects upfront in attempt to reduce play latency
def load_drumkit():
    kit_name = kits['kit_names'][kit_index]
    for i in range(num_pads):
        fname = kits[kit_name][i]
        waves[i] = audiocore.WaveFile(open(fname,"rb"))  #

# play a drum sample, either by sequencer or pressing pads
def play_drum(num, pressed):
    pads_lit[num] = pressed
    voice = mixer.voice[num]   # get mixer voice
    if pressed and not pads_mute[num]:
        voice.play(waves[num],loop=False)
    else: # released
        pass   # not doing this for samples

#
# MIDI
#

# Get midi from UART or USB
def midi_receive():
    while msg := midi_uart_in.receive() or midi_usb_in.receive():  # walrus!
        if msg is not None:
            print(time.monotonic(), msg)
            if isinstance(msg, NoteOn) and msg.velocity:
                print("noteOn:",msg.note, msg.note % 12)
                play_drum( msg.note % 12, True)
            if isinstance(msg,NoteOff) or (isinstance(msg, NoteOn) and msg.velocity==0):
                play_drum( msg.note % 12, False)


#
# startup
#

# load settings from disk
patterns = load_patterns()
kits = find_kits()

if debug: print("patterns",patterns)

# sequencer state
step_millis = 0 # derived from bpm, changed by "update_step_millis()" below
last_step_millis = ticks_ms()
seq_pos = 0  # where in our sequence we are
playing = False
recording = False

sequence = patterns[patt_index]['seq']  # sequence is array of [1,0,1,0]
num_steps = len(sequence[0])  # number of steps, based on length of first stepline

# drumkit state
kit_index = 0
waves = [None] * num_pads

# UI state
pads_lit = [0] * num_pads  # list of drum keys that are being played
pads_mute = [0] * num_pads # which pads are muted
pads_played = [0] * num_pads
last_led_millis = ticks_ms()  # last time we updated the LEDs
rec_held = False  # is REC button held, for deleting tracks
rec_held_used = False
mute_held = False  # is MUTE button held, for muting/unmuting tracks
tap_held = False  # is TAP/TEMPO button held
enc_sw_press_millis = 0
encoder_val_last = encoder.position
encoder_mode = 0  # 0 = change pattern, 1 = change kit, 2 = change bpm
led_min = 5  # how much to fade LEDs by
led_fade = 10 # how much to fade LEDs by

load_drumkit()
update_step_millis()

disp_bpm(bpm)
disp_play(playing,recording)
disp_pattern( patterns[patt_index]['name'] )
disp_kit( kits['kit_names'][kit_index] )
disp_encmode( encoder_mode )

print("macropadsynthplug drum machine ready!  bpm:", bpm, "step_millis:", step_millis, "steps:", num_steps)

while True:

    # midi_receive()

    now = ticks_ms()

    enc_sw_held = enc_sw_press_millis !=0  and (now - enc_sw_press_millis > 500)

    # LED handling
    if ticks_diff(now, last_led_millis) > 10:  # update every 10 msecs
        last_led_millis = now
        if enc_sw_held:  # edit mode
            leds[key_PLAY] = 0x44FF00
            leds[key_RECORD] = 0xFF4400
            leds[key_MUTE] = 0x0044FF
        else:
            leds[key_PLAY]   = 0x00FF00 if playing else 0x114400
            leds[key_RECORD] = 0xFF0044 if rec_held else 0xFF0000 if recording else 0x440011
            leds[key_MUTE]   = 0x001144  # mute mode button

            for i in range(num_pads):  # light up pressed drumpads
                if mute_held:  # show mute state instead
                    leds[ keynum_to_padnum.index(i) ] = 0x000000 if pads_mute[i] else 0x001144
                elif rec_held:
                    leds[ keynum_to_padnum.index(i) ] = 0xAA0022
                elif tap_held and not playing:  # light up special mode if holding taptemp button
                    leds[ keynum_to_padnum.index(i) ] = 0x111111
                if pads_lit[i]:   # also show pads being triggered, in nice JP-approved rainbows
                    leds[ keynum_to_padnum.index(i) ] = rainbowio.colorwheel( int(time.monotonic() * 20) )

        leds[:] = [[max(i-led_fade,led_min) for i in l] for l in leds] # fade released drumpads slowly
        leds.show()

    # Sequencer playing
    diff = ticks_diff( now, last_step_millis )
    if diff >= step_millis:
        late_millis = ticks_diff( diff, step_millis )  # how much are we late
        last_step_millis = ticks_add( now, -(late_millis//2) ) # attempt to make it up on next step

        # play any sounds recorded for this step
        if playing:
            for i in range(num_pads):
                if not pads_played[i]: # but play only if we didn't just play it
                    play_drum(i, sequence[i][seq_pos] ) # FIXME: what about note-off
                pads_played[i] = 0
            if(debug): print("%2d %3d " % (late_millis,seq_pos), [sequence[i][seq_pos] for i in range(num_pads)])

        # tempo indicator (leds.show() called by LED handler)
        if seq_pos % steps_per_beat == 0: leds[key_TAP_TEMPO] = 0x333333
        if seq_pos == 0: leds[key_TAP_TEMPO] = 0x3333FF # first beat indicator

        seq_pos = (seq_pos + 1) % num_steps # FIXME: let user choose?

    # Key handling
    key = keys.events.get()
    if key:
        keynum = key.key_number

        if keynum == key_PLAY:
            if key.pressed:
                if not enc_sw_held:  # normal play behavior
                    playing = not playing
                    if playing:
                        last_playing_millis = ticks_add(now, -step_millis)  # start playing!
                        seq_pos = 0
                    else:  # we are stopped
                        recording = False # so turn off recording too
                        for i in range(num_pads):
                            play_drum(i,0)
                    disp_play(playing,recording)
                else:
                    disp_info("copy patt")
                    copy_current_pattern()
                    disp_pattern( patterns[patt_index]['name'] )
                    disp_info("")

        elif keynum == key_RECORD:
            if key.pressed:
                if not enc_sw_held:  # normal record behavior
                    rec_held = True
                    rec_held_used = False
                else:
                    disp_info("save patts")
                    save_patterns()
                    disp_info("")

            if key.released and not enc_sw_held:
                rec_held = False
                if not rec_held_used:
                    recording = not recording # toggle record state
                    disp_play(playing,recording)

        elif keynum == key_MUTE:
            mute_held = key.pressed

        elif keynum == key_TAP_TEMPO:
            tap_held = key.pressed

        else: # else its a drumpad, either trigger, erase track, or mute track
            padnum = keynum_to_padnum[keynum]
            if key.pressed:
                # if REC button held while pad press, erase track
                if rec_held:
                    rec_held_used = True
                    for i in range(num_steps):
                        sequence[padnum][i] = 0
                # if MUTE button held, mute/unmute track
                elif mute_held:
                    pads_mute[padnum] = not pads_mute[padnum]
                # else trigger drum
                else:
                    play_drum( padnum, 1 )
                    if recording:
                        pads_played[padnum] = 1
                        # fix up the quantization on record
                        diff = ticks_diff( ticks_ms(), last_step_millis )
                        if debug: print("*"*30, " diff:", diff)
                        save_pos = seq_pos -1
                        if diff > step_millis//2:  #
                            save_pos += 1
                        sequence[padnum][save_pos] = 1   # save it
                    # and start recording on the beat if set to record
                    if recording and not playing:
                        playing = True
                        last_playing_millis = ticks_add(ticks_ms(), -step_millis)
                        seq_pos = 0

            if key.released:
                play_drum( padnum, 0 ) # don't strictly need this

    # Encoder push handling
    enc_sw = encoder_switch.events.get()
    if enc_sw:
        if enc_sw.pressed:
            enc_sw_press_millis = now
        if enc_sw.released:
            if not enc_sw_held:  # press & release not press-hold
                encoder_mode = (encoder_mode + 1) % 3  # only 3 modes for encoder currently
                disp_encmode(encoder_mode)
                disp_info("")
            enc_sw_press_millis = 0


    # Encoder turn handling
    encoder_val = encoder.position
    if encoder_val != encoder_val_last:
        encoder_delta = (encoder_val - encoder_val_last)
        encoder_val_last = encoder_val
        if encoder_mode == 0:  # mode 1 == change pattern
            patt_index = (patt_index + encoder_delta) % len(patterns)
            sequence = patterns[patt_index]['seq']
            disp_pattern( patterns[patt_index]['name'] )
        elif encoder_mode == 1:  # mode 1 == change kit
            kit_index = (kit_index + encoder_delta) % len(kits['kit_names'])
            load_drumkit()
            disp_kit( kits['kit_names'][kit_index] )
        elif encoder_mode == 2:  # mode 0 == update BPM
            bpm += encoder_delta
            update_step_millis()
            disp_bpm(bpm)
