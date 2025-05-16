# MacroPadSynthPlug!

Turn MacroPad RP2040's StemmaQT port into Audio Out + MIDI In

<a href="https://www.tindie.com/products/todbot/macropadsynthplug-turn-rp2040-into-a-synth/"><img src="https://d2ss6ovg47m0r5.cloudfront.net/badges/tindie-smalls.png" alt="PicoTouch on Tindie" width="200" height="55"></a>

Demo video on Youtube:
[![CircuitPython drum machine demo](https://img.youtube.com/vi/jMKC_18M17U/maxresdefault.jpg)](https://www.youtube.com/watch?v=jMKC_18M17U)


## What is this?

The [Adafruit MacroPad RP2040](https://learn.adafruit.com/adafruit-macropad-rp2040/overview)
is really fun and could be a great musical instrument,
with its 12 keys, rotary encoder, OLED display, RP2040 chip, and 8MB of flash storage.

If it only had a way to get MIDI into it and Audio out of it!
Well now you can, with MacroPadSynthPlug!

MacroPadSynthPlug is a small board that plugs into a StemmaQT / Qwiic port
and gives you [TRS-A MIDI In](https://minimidi.world/) and Audio line out.
It's not I2C, but is using those pins. 

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

But with the MacroPad RP2040, the two StemmaQT pins have the possible functionality:

- SDA - GP20 - UART1 TX - PWM2B
- SCL - GP21 - UART1 RX - PWM2A

This means we could use the StemmaQT port for all sorts of musical things, like:

- MIDI In / MID Out!
- Stereo PWM Audio Out!
- MIDI In / Audio Out!  *(Hey this is what MacroPadSynthPlug does)*

To get audio out, we need is a small PWM filtering circuit.
To get MIDI in, a small optoisolator circuit is needed.

MacroPadSynthPlug is those two circuits, wired like so:

- StemmaQT SCL -- TRS-A MIDI input
- StemmaQT SDA -- audio PWM out


This is an "abuse" of the StemmaQT port, as it's meant only for I2C devices.
But it's safe, will not damage other StemmaQT devices,
but it does mean you "lose" the StemmaQT port for it's normal use with I2C.


## Why?

Seems like fun?  I have built many RP2040-based little hardware synths, like:

- [PicoStepSeq](https://github.com/todbot/picostepseq)
- [picotouchsynth](https://github.com/todbot/picotouchsynth)
- [plinkykeeb](https://github.com/todbot/plinkykeeb)
- [seeknobs](https://github.com/todbot/seeknobs)

and wanted the MacroPad RP2040 to join in the fun.

## Does this work for other boards with StemmaQT?

Short answer: Yes, with caveats

* Boards that can do PWM audio out on the GPIO pin going to StemmaQT SDA 
  can use the Audio Out side of MacroPadSynthPlug, and do USB MIDI for MIDI input

* Boards that can do UART In on the GPIO pin for StemmaQT SCL can do TRS MIDI input


### Tested boards:

* Adafruit MacroPad RP2040 

* QTPy RP2040 with a PIO-based UART libary like [`SerialPIO`](https://arduino-pico.readthedocs.io/en/latest/piouart.html) or [`adafruit_pio_uart`](https://github.com/adafruit/Adafruit_CircuitPython_PIO_UART)

* Adadfruit KB2040 "Keeboar"

* Raspberry Pi Pico / Pico 2 with a [StemmaQT](https://www.adafruit.com/product/4209) / [Qwiic](https://www.sparkfun.com/flexible-qwiic-cable-breadboard-jumper-4-pin.html) breadboard jumper cable


## Are these for sale?

Yes! [Get one now at Tindie!](https://www.tindie.com/products/todbot/macropadsynthplug-turn-rp2040-into-a-synth/)

## Action shots

<img width=700 src="./docs/img_production1.jpg">

<img width=700 src="./docs/img1.jpg">
<img width=700 src="./docs/img2.jpg">
