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
import displayio, terminalio
import rainbowio
import neopixel
import audiocore, audiomixer, audiopwmio
from adafruit_ticks import ticks_ms, ticks_diff, ticks_add
from adafruit_display_text.bitmap_label import Label
import usb_midi
import adafruit_midi
from adafruit_midi.note_on import NoteOn
from adafruit_midi.note_off import NoteOff

from drum_patterns import patterns_demo

#time.sleep(3) # wait for USB connect a bit to avoid terible audio glitches

use_macrosynthplug = False  # False to use built-in speaker of MacroPad RP2040
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
# maybe we invert this, since we call .index() more often

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


# display setup begin
dw,dh = 64,128
display = board.DISPLAY
display.rotation = 90
font = terminalio.FONT
dispgroup = displayio.Group()
display.show(dispgroup)
txt1 = Label(font, text="macropad",      x=0,  y=10)
txt2 = Label(font, text="synthplug",     x=0,  y=20)
txt3 = Label(font, text="drumachine",    x=0,  y=30)

txt_mode_val = Label(font, text="stop",  x=40, y=45)

txt_emode0 = Label(font,text=">",        x=0,  y=55)
txt_patt = Label(font, text="patt",      x=6,  y=55)
txt_emode1 = Label(font,text=" ",        x=0,  y=70)
txt_kit = Label(font, text="kit:",       x=6,  y=70)
#txt_kit_val = Label(font, text="kitt",   x=6,  y=85)
txt_emode2 = Label(font,text=" ",        x=0,  y=85)
txt_bpm = Label(font, text="bpm:",       x=6,  y=85)
txt_bpm_val = Label(font, text=str(bpm), x=35, y=85)

txt_rcv = Label(font, text="midi:",      x=0, y=115)
txt_info = Label(font, text="   ",    x=10, y=122)
for t in (txt1, txt2, txt3, txt_mode_val, txt_emode0, txt_emode1, txt_emode2,
          txt_patt, txt_kit, txt_bpm, txt_bpm_val, txt_rcv, txt_info):
    dispgroup.append(t)
# display setup end

#
# Sequence management
#

def make_sequence_from_demo_pattern(p):
    sq = []
    for i in range(p['len']):  # FIXME: maybe 'base_len'? no but
        stepline_str = p['base'][i % len(p['base'])] # get step line in base seq, maybe repeating
        # convert str of '1010' to array 1,0,1,0, eliding whitespace, for all seq lines
        stepline_str = stepline_str.replace(' ', '')  # collapse any whitespace
        stepline = [int(c) for c in stepline_str]
        sq.append( stepline ) # convert binary string to array of 1,0
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
    for i in range(len(patterns)):
        patts_to_sav.append( { 'name':patterns[i]['name'], 'seq':seq_str } )
    with open('/test_saved_patterns.json', 'w') as fp:
        json.dump(patts_to_sav, fp)
    print("done")

def load_patterns():
    patts = []
    try:
        with open("/saved_patterns.json",'r') as fp:
            patts = json.load(fp)
            for p in patts:
                # convert str of '1010' to array 1,0,1,0, eliding whitespace, for all seq lines
                p['seq'] = [int(c) for c in s.replace(' ','') for s in p['seq']]
    except (OSError, ValueError) as error:  # maybe no file
        print("ERROR: load_patterns:",error)
    if len(patts) == 0: # load demo
        print("no saved patterns, loading demo patterns")
        patts = patterns_demo
        for p in patts:
            p['seq'] = make_sequence_from_demo_pattern(p)

    return patts  # not strictly needed currently, but wait for it...

# for debugging, print out current sequence when stopped
def print_sequence(fp,pat):
    seq = pat['seq']
    fp.write("  {\n")
    fp.write("    'name':'%s',\n" % pat['name'])
    fp.write("    'len': %d,\n" % len(seq) )
    fp.write("    'seq': [\n")
    for i in range(len(seq)):
        fp.write(f"       '{seq[i]:08b}',\n") # make string
    fp.write("    ],\n");
    fp.write("  },\n")

def print_patterns():
    with sys.stdout as fp:
    #with open("/newpatterns.py", "w") as fp:
        fp.write("[\n")
        for p in patterns:
            print_sequence(fp,p)
        fp.write("]\n")

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
        pass   # not doing this


#
# Display updates
#

# update step_millis and display
def update_bpm():
    global step_millis
    # Beat timing assumes 4/4 time signature, e.g. 4 beats per measure, 1/4 note gets the beat
    beat_time = 60 / bpm  # time length of a single beat
    beat_millis = beat_time * 1000  # time length of single beat in milliseconds
    step_millis = int(beat_millis / steps_per_beat)  # time length of a beat subdivision, e.g. 1/16th note
    txt_bpm_val.text = str(bpm)
    # and keep "step_millis" an int so diff math is fast

# update display
def update_play():
    if playing:
        txt_mode_val.text = "play" if not recording else "odub"
    else:
        txt_mode_val.text = "stop" if not recording else "reco"  # FIXME:

# update display
def update_pattern():
    txt_patt.text = patterns[patt_index]['name']

def update_kit():
    txt_kit.text = kits['kit_names'][kit_index]

# update display
def update_encmode():
    txt_emode0.text = '>' if encoder_mode==0 else ' '
    txt_emode1.text = '>' if encoder_mode==1 else ' '
    txt_emode2.text = '>' if encoder_mode==2 else ' '

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

print("patterns",patterns)
#print_patterns()

# sequencer state
step_millis = 0 # derived from bpm, changed by "update_bpm()" below
last_step_millis = ticks_ms()
seq_pos = 0  # where in our sequence we are
playing = False
recording = False

sequence = patterns[patt_index]['seq']  # sequence is array of [1,0,1,0]
num_steps = len(sequence)  # number of steps

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

load_drumkit()

update_bpm()
update_play()
update_pattern()
update_kit()
update_encmode()

print("macropadsynthplug drum machine ready!  bpm:", bpm, "step_millis:", step_millis, "steps:", num_steps)
led_min = 5
led_fade = 10

while True:

    # midi_receive()

    now = ticks_ms()

    # LED handling
    if ticks_diff(now, last_led_millis) > 10:  # update every 10 msecs
        last_led_millis = now
        leds[key_PLAY]   = 0x00FF00 if playing else 0x114400
        #leds[key_RECORD] = 0xFF0000 if recording else 0x440044 if rec_held else 0x441100
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
                    play_drum(i, sequence[seq_pos][i] ) # FIXME: what about note-off
                pads_played[i] = 0
            if(debug): print(f"{late_millis:02d} {seq_pos:3d} {sequence[seq_pos]}")

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
                playing = not playing
                if playing:
                    last_playing_millis = ticks_add(now, -step_millis)  # start playing!
                    seq_pos = 0
                else:  # we are stopped
                    recording = False # so turn off recording too
                    for i in range(num_pads):
                        play_drum(i,0)
                update_play()

        elif keynum == key_RECORD:
            if key.pressed:
                rec_held = True
                rec_held_used = False
            if key.released:
                rec_held = False
                if not rec_held_used:
                    recording = not recording # toggle record state
                    update_play()

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
                        sequence[i][padnum] = 0
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
                        sequence[ save_pos ][padnum] = 1   # save it
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
            if (now - enc_sw_press_millis) < 2000:  # press & release not press-hold
                encoder_mode = (encoder_mode + 1) % 3  # only 3 modes for encoder currently
                update_encmode()
            else:
                txt_info.text = ''
            enc_sw_press_millis = 0

    if enc_sw_press_millis and (now - enc_sw_press_millis) > 2000: # press-hold == save patterns
        txt_info.text = "saving"
        save_patterns()

    # Encoder turn handling
    encoder_val = encoder.position
    if encoder_val != encoder_val_last:
        encoder_delta = (encoder_val - encoder_val_last)
        encoder_val_last = encoder_val
        if encoder_mode == 0:  # mode 1 == change pattern
            patt_index = (patt_index + encoder_delta) % len(patterns)
            print("pattern:", patt_index)
            #sequence = make_sequence(patterns[patt_index])
            sequence = patterns[patt_index]['seq']
            update_pattern()
        elif encoder_mode == 1:  # mode 1 == change kit
            kit_index = (kit_index + encoder_delta) % len(kits['kit_names'])
            load_drumkit()
            update_kit()
        elif encoder_mode == 2:  # mode 0 == update BPM
            bpm += encoder_delta
            update_bpm()
