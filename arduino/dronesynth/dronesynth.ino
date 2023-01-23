/**
 * dronesynth.ino - Multi oscillator drone synth for MacroPad RP2040 w/ MacroPadSynthPlug
 *  
 * 22 Jan 2023 - @todbot / Tod Kurt
 * Part of MacroPadSynthPlug: https://github.com/todbot/macropadsynthplug/
 */

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
uint8_t resonance = 120; // range 0-255, 255 is most resonant
uint8_t cutoff = 70;
int portamento_time = 500;


#include "macropad_ui.h"

// core0 setup
void setup() {
 lpf.setCutoffFreqAndResonance(cutoff, resonance);
  for( int i=0; i<NUM_OSCS; i++) { 
     aOscs[i].setTable(SAW_ANALOGUE512_DATA);
     portamentos[i].setTime(100);
  }
  startMozzi();
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
    r = (scatterMode) ? r*10 : r;
    portamentos[i].start( float_to_Q16n16(note) + r );  // + r
  }  
}

// Mozzi function, called every CONTROL_RATE
void updateControl() {
  
  // filter range (0-255) corresponds with 0-8191Hz
  // oscillator & mods run from -128 to 127
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
  //uint8_t b = 0; // count number of active oscillators
  for( int i=0; i<NUM_OSCS; i++) {
    int8_t a = aOscs[i].next();
    asig += a;
  }
  asig = lpf.next(asig);
  return MonoOutput::fromAlmostNBit(12, asig); // should be 12 
}
