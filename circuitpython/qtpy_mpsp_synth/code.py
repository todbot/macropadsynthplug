# qtpy_mpsp_synth_code.py -- demo QTPy RP2040 with MacroPadSynthPlug
# 16 May 2024 - Tod Kurt
import time, random
import board, busio
import audiopwmio, audiocore, audiomixer, synthio
import usb_midi
import tmidi
import adafruit_pio_uart

uart = adafruit_pio_uart.UART(tx=None, rx=board.SCL1, baudrate=31250, timeout=0.001)
midi_usb = tmidi.MIDI(midi_in=usb_midi.ports[0])
midi_uart = tmidi.MIDI(midi_in=uart)

audio = audiopwmio.PWMAudioOut(board.SDA1)
mixer = audiomixer.Mixer(sample_rate=32000, channel_count=1, buffer_size=2048)
synth = synthio.Synthesizer(sample_rate=32000, channel_count=1)
audio.play(mixer)
mixer.voice[0].play(synth)

amp_env = synthio.Envelope(attack_time=0.02, decay_time=0.2, release_time=0.3,
                           attack_level=0.8, sustain_level=0.4)
synth.envelope = amp_env

print("here we go")
while True:
    # receive MIDI from either TRS MIDI or USB MIDI 
    if msg := (midi_uart.receive() or  midi_usb.receive()):
        if msg.type == tmidi.NOTE_ON and msg.velocity > 0:
            synth.press(msg.note)
            print("press:  ", msg.note)
        elif msg.type == tmidi.NOTE_OFF or msg.velocity == 0:
            synth.release(msg.note)
            print("release:", msg.note)
