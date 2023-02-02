/**
 * monosynth1 wubwubwub synth using LowPassFilter
 * based MozziScout "mozziscout_monosynth1"
 *
 * Responds to USB MIDI and (soon) Serial (DIN) MIDI In
 *
 * Must edit Mozzi library!
 * - in "Mozzi/AudioConfigRP2040.h"
 *   - change to "AUDIO_CHANNEL_1_PIN 20"
 *   - or change to "AUDIO_CHANNEL_1_PIN 16" for built-in speaker (
 *      (must also set pin 14 HIGH to enable built-in speaker)
 * 
 * IDE change:
 * - Select "Tools / USB Stack: Adafruit TinyUSB" * 
 * - Select "Tools / Flash Size: 2MB (Sketch: 1MB / FS: 1MB)
 *  
 *  @todbot 20 Jan 2023
 **/

// Mozzi's controller update rate, seems to have issues at 1024
// If slower than 512 can't get all MIDI from Live
#define CONTROL_RATE 512 
// set DEBUG_MIDI 1 to show CCs received in Serial Monitor
#define DEBUG_MIDI 0

#include <MozziGuts.h>
#include <Oscil.h>
#include <tables/triangle_analogue512_int8.h>
#include <tables/square_analogue512_int8.h>
#include <tables/saw_analogue512_int8.h>
#include <tables/cos2048_int8.h> // for filter modulation
#include <LowPassFilter.h>
#include <ADSR.h>
#include <Portamento.h>
#include <mozzi_midi.h> // for mtof()

#include <Adafruit_TinyUSB.h>
#include <MIDI.h>


// SETTINGS
//int portamento_time = 50;  // milliseconds
//int env_release_time = 1000; // milliseconds
byte sound_mode = 0; // patch number / program change
bool retrig_lfo = true;

enum KnownCCs {
  Modulation=0,
  Resonance,
  FilterCutoff,
  PortamentoTime,
  EnvReleaseTime,
  CC_COUNT
};

// mapping of KnownCCs to MIDI CC numbers (this is somewhat standardized)
uint8_t midi_ccs[] = {
  1,   // modulation
  71,  // resonance
  74,  // filter cutoff
  5,   // portamento time
  72,  // env release time
};
uint8_t mod_vals[ CC_COUNT ];

const int midi_rx_pin = PIN_WIRE0_SCL; // GPIO21 on StemmaQt connector
Adafruit_USBD_MIDI usb_midi;  // USB MIDI object
MIDI_CREATE_INSTANCE(Adafruit_USBD_MIDI, usb_midi, MIDIusb); // USB MIDI
MIDI_CREATE_INSTANCE(HardwareSerial, Serial1, MIDIserial);   // Serial MIDI

//
Oscil<SAW_ANALOGUE512_NUM_CELLS, AUDIO_RATE> aOsc1(SAW_ANALOGUE512_DATA);
Oscil<SAW_ANALOGUE512_NUM_CELLS, AUDIO_RATE> aOsc2(SAW_ANALOGUE512_DATA);

Oscil<COS2048_NUM_CELLS, CONTROL_RATE> kFilterMod(COS2048_DATA); // filter mod

ADSR <CONTROL_RATE, AUDIO_RATE> envelope;
Portamento <CONTROL_RATE> portamento;
LowPassFilter lpf;

//
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);

  // USB and MIDI setup
  Serial1.setRX(midi_rx_pin);
  MIDIserial.begin(MIDI_CHANNEL_OMNI);
  MIDIserial.turnThruOff(); // turn off echo
  
  MIDIusb.begin(MIDI_CHANNEL_OMNI);
  MIDIusb.turnThruOff();    // turn off echo
  // USB and MIDI end
  
  Serial.begin(115200);
  
  startMozzi(CONTROL_RATE);

  handleProgramChange(0); // set our initial patch
}

//
void loop() {
  audioHook();
}

void handleMIDI() {
  handleMIDIusb();
  handleMIDIserial();
}

//
void handleMIDIusb() {
  while( MIDIusb.read() ) {  // use while() to read all pending MIDI, shouldn't hang
    switch(MIDIusb.getType()) {
      case midi::ProgramChange:
        handleProgramChange(MIDIusb.getData1());
        break;
      case midi::ControlChange:
        handleControlChange(0, MIDIusb.getData1(), MIDIusb.getData2());
        break;
      case midi::NoteOn:
        handleNoteOn( 0, MIDIusb.getData1(),MIDIusb.getData2());
        break;
      case midi::NoteOff:
        handleNoteOff( 0, MIDIusb.getData1(),MIDIusb.getData2());
        break;
      default:
        break;
    }
  }
}
// surely there's a way to have this generalized
void handleMIDIserial() {
  while( MIDIserial.read() ) {  // use while() to read all pending MIDI, shouldn't hang
    switch(MIDIserial.getType()) {
      case midi::ProgramChange:
        handleProgramChange(MIDIserial.getData1());
        break;
      case midi::ControlChange:
        handleControlChange(0, MIDIserial.getData1(), MIDIserial.getData2());
        break;
      case midi::NoteOn:
        handleNoteOn( 0, MIDIserial.getData1(),MIDIserial.getData2());
        break;
      case midi::NoteOff:
        handleNoteOff( 0, MIDIserial.getData1(),MIDIserial.getData2());
        break;
      default:
        break;
    }
  }
}

//
void handleNoteOn(byte channel, byte note, byte velocity) {
//  Serial.println("midi_test handleNoteOn!");
  digitalWrite(LED_BUILTIN,HIGH);
  portamento.start(note);
  envelope.noteOn();
}

//
void handleNoteOff(byte channel, byte note, byte velocity) {
  digitalWrite(LED_BUILTIN,LOW);
  envelope.noteOff();
}

//
void handleControlChange(byte channel, byte cc_num, byte cc_val) {
  #if DEBUG_MIDI 
  Serial.printf("CC %d %d\n", cc_num, cc_val);
  #endif
  for( int i=0; i<CC_COUNT; i++) { 
    if( midi_ccs[i] == cc_num ) { // we got one
      mod_vals[i] = cc_val;
      // special cases, not set every updateControl()
      if( i == PortamentoTime ) { 
        portamento.setTime( mod_vals[PortamentoTime] * 2);
      }
      else if( i == EnvReleaseTime ) {
         envelope.setReleaseTime( mod_vals[EnvReleaseTime]*10 );
      }
    }
  }
}

//
void handleProgramChange(byte m) {
  Serial.print("program change:"); Serial.println((byte)m);
  sound_mode = m;
  if( sound_mode == 0 ) {    
    aOsc1.setTable(SAW_ANALOGUE512_DATA);
    aOsc2.setTable(SAW_ANALOGUE512_DATA);
    
    mod_vals[Modulation] = 0;   // FIXME: modulation unused currently
    mod_vals[Resonance] = 93;
    mod_vals[FilterCutoff] = 60;
    mod_vals[PortamentoTime] = 50; // actually in milliseconds
    mod_vals[EnvReleaseTime] = 100; // in 10x milliseconds (100 = 1000 msecs)

    lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);
    
    kFilterMod.setFreq(4.0f);  // fast
    envelope.setADLevels(255, 255);
    envelope.setTimes(50, 200, 20000, mod_vals[EnvReleaseTime] );
    portamento.setTime( mod_vals[PortamentoTime] );
  }
  else if ( sound_mode == 1 ) {
    aOsc1.setTable(SQUARE_ANALOGUE512_DATA);
    aOsc2.setTable(SQUARE_ANALOGUE512_DATA);
    
    mod_vals[Resonance] = 50;
    mod_vals[EnvReleaseTime] = 15;
    
    lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);
    
    kFilterMod.setFreq(0.5f);     // slow
    envelope.setADLevels(255, 255);
    envelope.setTimes(50, 100, 20000, (uint16_t)mod_vals[EnvReleaseTime]*10 );
    portamento.setTime( mod_vals[PortamentoTime] );
  }
  else if ( sound_mode == 2 ) {
    aOsc1.setTable(TRIANGLE_ANALOGUE512_DATA);
    aOsc2.setTable(TRIANGLE_ANALOGUE512_DATA);
    mod_vals[FilterCutoff] = 65;
    //kFilterMod.setFreq(0.25f);    // slower
    //retrig_lfo = false;
  }
}

// mozzi function, called at CONTROL_RATE times per second
void updateControl() {
  handleMIDI();
  
  // map the lpf modulation into the filter range (0-255), corresponds with 0-8191Hz, kFilterMod runs -128-127
  //uint8_t cutoff_freq = cutoff + (mod_amount * (kFilterMod.next()/2));
//  uint16_t fm = ((kFilterMod.next() * mod_vals[Modulation]) / 128) + 127 ; 
//  uint8_t cutoff_freq = constrain(mod_vals[FilterCutoff] + fm, 0,255 );
  
//  lpf.setCutoffFreqAndResonance(cutoff_freq, mod_vals[Resonance]*2);

  lpf.setCutoffFreqAndResonance(mod_vals[FilterCutoff], mod_vals[Resonance]*2);  // don't *2 filter since we want 0-4096Hz

  envelope.update();
  
  Q16n16 pf = portamento.next();  // Q16n16 is a fixed-point fraction in 32-bits (16bits . 16bits)
  aOsc1.setFreq_Q16n16(pf);
  aOsc2.setFreq_Q16n16(pf*1.02);

}

// mozzi function, called at AUDIO_RATE times per second
AudioOutput_t updateAudio() {
  long asig = lpf.next( aOsc1.next() + aOsc2.next() );
  return MonoOutput::fromAlmostNBit(18, envelope.next() * asig); // 16 = 8 signal bits + 8 envelope bits
}
