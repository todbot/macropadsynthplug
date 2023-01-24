/**
 * dronesynth.ino - Multi oscillator drone synth for MacroPad RP2040 w/ MacroPadSynthPlug
 *  
 * 22 Jan 2023 - @todbot / Tod Kurt
 * Part of MacroPadSynthPlug: https://github.com/todbot/macropadsynthplug/
 *
 * Libraries needed (all available via Library Manager):
 * - Bounce2 -- https://github.com/thomasfredericks/Bounce2
 * - RotaryEncoder -- http://www.mathertel.de/Arduino/RotaryEncoderLibrary.aspx
 * - Adafruit_SSD1306 -- https://github.com/adafruit/Adafruit_SSD1306
 * - Adafruit_TinyUSB -- https://github.com/adafruit/Adafruit_TinyUSB_Arduino
 * - MIDI -- https://github.com/FortySevenEffects/arduino_midi_library
 *
* Must edit Mozzi library!
 * - in "Mozzi/AudioConfigRP2040.h"
 *   - change to "AUDIO_CHANNEL_1_PIN 20" for MacroPadSynthPlug
 *   - or change to "AUDIO_CHANNEL_1_PIN 16" for built-in speaker  
 *      (must also set pin 14 HIGH to enable built-in speaker) 
 * 
 * IDE change:
 * - Select "Tools / USB Stack: Adafruit TinyUSB" * 
 * - Select "Tools / Flash Size: 2MB (Sketch: 1MB / FS: 1MB)
 */

#include "macropad_ui.h"

//#define CONTROL_RATE 128   // sets update rate of Mozzi's updateControl() function
#include <MozziGuts.h>
#include <Oscil.h>
#include <tables/saw_analogue512_int8.h> // oscillator waveform
#include <tables/cos2048_int8.h> // filter modulation waveform
#include <LowPassFilter.h>
#include <Portamento.h>
#include <mozzi_rand.h>  // for rand()
#include <mozzi_midi.h>  // for mtof()

#define NUM_OSCS 12  // same as NUM_KEYS, for now

Oscil<SAW_ANALOGUE512_NUM_CELLS, AUDIO_RATE> aOscs [NUM_OSCS];
Portamento <CONTROL_RATE> portamentos[NUM_OSCS];

LowPassFilter lpf;
uint8_t resonance = 140; // range 0-255, 255 is most resonant
uint8_t cutoff = 70;
int portamento_time = 400;


// core0 setup
void setup() {
  // USB and MIDI
  USBDevice.setManufacturerDescriptor("todbot");
  USBDevice.setProductDescriptor     ("DroneSynth");

  //  Serial1.setRX(midi_rx_pin);
  MIDIusb.begin(MIDI_CHANNEL_OMNI);
  //  MIDIserial.begin(MIDI_CHANNEL_OMNI);
  MIDIusb.turnThruOff();    // turn off echo
  //  MIDIserial.turnThruOff(); // turn off echo
  // USB and MIDI end
    
  Serial.begin(115200);
 
  lpf.setCutoffFreqAndResonance(cutoff, resonance);
  for( int i=0; i<NUM_OSCS; i++) { 
     aOscs[i].setTable(SAW_ANALOGUE512_DATA);
     portamentos[i].setTime(100);
  }
  startMozzi();
  
  Serial.println("dronetest");
}

// core0 loop() belongs to Mozzi
void loop() {
  audioHook();
}

//
void setOscs() {  
  bool noteMode = false;
  for(int i=0; i<NUM_OSCS; i++) {
    float note = root_note + 24 * ((float)osc_vals[i] / MAX_TUNE); 
    Q15n16 r = Q7n8_to_Q15n16(100-rand(200)); // random for oscillator "drift".
    if( scatterAmount ) {
      r = r * (scatterAmount*2);
    }
    portamentos[i].start( float_to_Q16n16(note) + r );  // + r
  }  
}

// Mozzi function, called every CONTROL_RATE
void updateControl() {
  
  // filter range (0-255) corresponds with 0-8191Hz
  // oscillator & mods run from -128 to 127
  cutoff = filterAmount; // copy from UI
  lpf.setCutoffFreqAndResonance(cutoff, resonance);

  for(int i=0; i<NUM_OSCS; i++) {
    portamentos[i].setTime( portamento_time );
    Q16n16 f = portamentos[i].next();
    aOscs[i].setFreq_Q16n16(f);
  }
 
  setOscs();
}

// mozzi function, called every AUDIO_RATE to output sample
AudioOutput_t updateAudio() {
  int16_t asig = (long) 0;
  for( int i=0; i<NUM_OSCS; i++) {
    int8_t a = aOscs[i].next();
    asig += a;
  }
  asig = lpf.next(asig) * volumeAmount;  // volume 0-15 adds 4-bits 
  return MonoOutput::fromAlmostNBit(15, asig); // should be 12? 
}
