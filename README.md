# MacroPadSynthPlug!

abuse MacroPad RP2040's StemmaQT port by turning it into Audio Out + MIDI In

[Get one now at Tindie!](https://www.tindie.com/products/todbot/macropadsynthplug-turn-rp2040-into-a-synth/)

Demo video on Youtube:
[![CircuitPython drum machine demo](https://img.youtube.com/vi/jMKC_18M17U/maxresdefault.jpg)](https://www.youtube.com/watch?v=jMKC_18M17U)


## What is this?

The [Adafruit MacroPad RP2040](https://learn.adafruit.com/adafruit-macropad-rp2040/overview)
is really fun and could be a great musical instrument,
with its 12 keys, rotary encoder, OLED display, RP2040 chip, and 8MB of flash storage.

If it only had a way to get MIDI into it and Audio out of it!
Well now you can, with MacroPadSynthPlug!

MacroPadSynthPlug is a small board that plugs into the StemmaQT port (but is not I2C!)
and gives you [TRS-A MIDI In](https://minimidi.world/) and Audio line out.

The MacroPad RP2040 can now be a stand-alone MIDI synth!

Examples provided for both [CircuitPython](https://circuitpython.org/) and [Arduino](https://arduino-pico.readthedocs.io/en/latest/):


* __drum_machine__ - CircuitPython-based drum sequencer ([demo1](https://youtu.be/jMKC_18M17U),[demo2](https://youtu.be/bJwyUjxc6VM) )
* __dronesynth__ - Arduino Mozzi 12-oscillator drone synth ([demo](https://youtu.be/kLwP-vyvtLM))
* __remixer__ - CircuitPython-based song remixer ([source](https://github.com/todbot/macropadsynthplug/tree/main/circuitpython/remixer))
* __monosynth1__ - Arduino Mozzi 2-oscillator bass monosynth w/ resonant low-pass filter ([source](https://github.com/todbot/macropadsynthplug/tree/main/arduino/monosynth1))


## How?

The [Raspberry Pi RP2040 chip](https://www.raspberrypi.com/documentation/microcontrollers/rp2040.html)
on the MacroPad RP2040 is amazingly configurable.

Normally a port like the StemmaQT I2C port would only be usable as an I2C bus, or maybe as GPIO pins.

But with the MacroPad RP2040, the two StemmaQT pins are:

- SDA - GP20 - UART1 TX - PWM2B
- SCL - GP21 - UART1 RX - PWM2A

This means we could use the StemmaQT port for all sorts of musical things, like:

- MIDI In / Out!
- Stereo PWM audio out!
- MIDI In / Audio Out  (Hey this is what MacroPadSynthPlug does)

To get audio out, all we need is a small PWM filtering circuit.
To get MIDI in, a small optoisolator circuit is needed.

MacroPadSynthPlug is just this.  It is wired like so:

- StemmaQT SCL -- TRS-A MIDI input
- StemmaQT SDA -- audio PWM out


This is sort of an "abuse" of the StemmaQT port, as it's meant only for I2C devices.
But it's safe, will not damage other StemmaQT devices,
but it does mean you "lose" the StemmaQT port for it's normal use.


## Why?

Seems like fun?  I have built many RP2040-based little hardware synths, like:
- [PicoStepSeq](https://github.com/todbot/picostepseq)
- [picotouchsynth](https://github.com/todbot/picotouchsynth)
- [plinkykeeb](https://github.com/todbot/plinkykeeb)
- [seeknobs](https://github.com/todbot/seeknobs)

and wanted the MacroPad RP2040 to join in the fun.

## Does this work for other boards with StemmaQT?

Short answer: not really

For any non-RP2040-based board, this almost definitely will not work.

And while the RP2040 is a very configuraable, not all functions are availbe on all pins.
So it probably won't work on other RP2040-based boards too.  For instance:

- QTPy RP2040?  Sorta. Its StemmaQT SDA/SCL is on GPIO22/23, which has PWM but no UART RX
- KB2040 "Keeboar"? Yes! Its StemmaQT SDA/SCL is on GPIO12/13, which has PWM & UART0 RX!


## Are these for sale?

Yes! [Get one now at Tindie!](https://www.tindie.com/products/todbot/macropadsynthplug-turn-rp2040-into-a-synth/)

## Action shots

<img width=700 src="./docs/img_production1.jpg">

<img width=700 src="./docs/img1.jpg">
<img width=700 src="./docs/img2.jpg">
