
#include <Wire.h>
#include <RotaryEncoder.h>
#include <Bounce2.h>
#include <Button2.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Fonts/FreeMono9pt7b.h>
#include <Fonts/FreeMonoBold12pt7b.h>
#include "Font5x7FixedMono.h"
#define myfont FreeMono9pt7b
#define myfont2 Font5x7FixedMono 
// see: https://learn.adafruit.com/adafruit-gfx-graphics-library/using-fonts
#include <Adafruit_TinyUSB.h>
#include <MIDI.h>


const int NUM_KEYS = 12;
const int DW = 128;
const int DH = 64;

const int MAX_TUNE = 96;

const int key_pins[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};

Bounce keys[NUM_KEYS];
Bounce encoder_switch;

const int midi_rx_pin = PIN_WIRE0_SCL; // GPIO21 on StemmaQt connector
Adafruit_USBD_MIDI usb_midi;  // USB MIDI object
MIDI_CREATE_INSTANCE(Adafruit_USBD_MIDI, usb_midi, MIDIusb); // USB MIDI
MIDI_CREATE_INSTANCE(HardwareSerial, Serial2, MIDIserial);   // Serial MIDI

Adafruit_NeoPixel leds = Adafruit_NeoPixel(NUM_KEYS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
Adafruit_SH1106G display = Adafruit_SH1106G(DW, DH, &SPI1, OLED_DC, OLED_RST, OLED_CS);

RotaryEncoder encoder(PIN_ROTB, PIN_ROTA, RotaryEncoder::LatchMode::FOUR3);
void checkEncoderPosition() {  encoder.tick(); } // just call tick() to check the state.

int encoder_pos = 0; // our encoder position state
uint32_t last_encoder_millis = 0;
bool keys_pressed[NUM_KEYS];
byte editMode = 0; // 0 = edit freqs, 1 = edit scattermode, 2 = edit volume

// values used by Mozzi on core0
byte rootNote = 48; // MIDI base note
int oscVals[ NUM_KEYS ];
byte volumeAmount = 15; // 0-15
byte scatterAmount = 0; // 0-50
byte filterAmount = 70;
bool droneMode = true;
//

int notenum_to_oct(int notenum) {
  return (notenum / 12) - 2;
}

const char* notenum_to_notestr(int notenum) {
  const char* note_strs[] = {"C ", "C#", "D ", "D#", "E ", "F ", // 0-12
                             "F#", "G ", "G#", "A ", "A#", "B ", "C ", }; 
  return note_strs[ notenum % 12 ];
}


// core1 runs UI and MIDI
void setup1() {
  delay(100);
  // OLED
  display.begin(0, true);
  display.clearDisplay();
  display.display();  // must clear before display, otherwise shows adafruit logo
  
  // LEDS
  leds.begin();
  leds.setBrightness(0.2 * 255);
  leds.fill(0x111111);
  leds.show(); // Initialize all pixels to 'off'

  // ENCODER
  pinMode(PIN_ROTA, INPUT_PULLUP);
  pinMode(PIN_ROTB, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ROTA), checkEncoderPosition, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ROTB), checkEncoderPosition, CHANGE);
  encoder_switch.attach(0, INPUT_PULLUP); // pin 0 is encoder switch pin

  // KEYS
  for (uint8_t i=0; i< NUM_KEYS; i++) {
    keys[i].attach( key_pins[i], INPUT_PULLUP);
  }

  for( int i=0; i<NUM_KEYS; i++ ) { 
    oscVals[i] = -24 + 12*rand(5);
  }
  
}

void midiHandleMsg( byte mtype, byte data1, byte data2, byte chan) {  
  if( mtype == midi::NoteOn ) {
    Serial.printf("noteON :%x\n",data1);
    rootNote = data1;
    portamento_time = 50;
    envelope.noteOn();
    droneMode = false;  // midi notes take us out of drone mode, turning root note knob puts us back
  }
  else if( mtype == midi::NoteOff ) {
    Serial.printf("noteOFF:%x\n",data1);
    envelope.noteOff();
    portamento_time = 400;
  }
}

void midiUsbReceive() {
  if ( !MIDIusb.read() ) { return; }

  byte mtype = MIDIusb.getType();
  byte data1 = MIDIusb.getData1();
  byte data2 = MIDIusb.getData2();
  byte chan  = MIDIusb.getChannel();

  //Serial.printf("MIDIusb c:%d t:%2x data:%2x %2x\n", chan, mtype, data1,data2);
  midiHandleMsg( mtype, data1, data2, chan);
}

void midiSerialReceive() {
  if ( !MIDIserial.read() ) { return; }

  byte mtype = MIDIserial.getType();
  byte data1 = MIDIserial.getData1();
  byte data2 = MIDIserial.getData2();
  byte chan  = MIDIserial.getChannel();

  Serial.printf("MIDIserial: c:%d t:%2x data:%2x %2x\n", chan, mtype, data1,data2);
  midiHandleMsg( mtype, data1, data2, chan);
}

void loop1() {
  // MIDI
  midiUsbReceive();
  midiSerialReceive();
   
  // KEYS
  for (uint8_t i=0; i< NUM_KEYS; i++) {
    keys[i].update();
    if(keys[i].fell() ) {  // active low
      keys_pressed[i] = true;
      Serial.printf("key %d pressed!\n", i);
      leds.setPixelColor(i, 0x0000ff);
    }
    if(keys[i].rose()) { // release
      keys_pressed[i] = false;
      leds.setPixelColor(i, 0x111111);
      Serial.print("oscVals: ");
      for(int i=0; i<NUM_KEYS; i++ ) { 
        Serial.print(oscVals[i]); Serial.print(" ");
      }
      Serial.println();
    }    
  }
  leds.show();
  
  // ENCODER
  encoder.tick();
  if( millis() - last_encoder_millis > 20 ) { 
    last_encoder_millis = millis();

    int newPos = encoder.getPosition();
    int deltaPos = newPos - encoder_pos;
    if( deltaPos ) {
      encoder_pos = newPos;
      Serial.printf("delta:%d\n",deltaPos);
      int dv = deltaPos*deltaPos*deltaPos; // cubic for fast turning
      // check to see if any keys are pressed, if so change their osc values
      bool keyed = false;
      for( int i=0; i<NUM_KEYS; i++ ) { 
        if( keys_pressed[i] ) { 
          oscVals[i] = constrain(oscVals[i] + dv, -MAX_TUNE,MAX_TUNE);
          keyed = true;
        }
      }
      // if no keys pressed, just turning knob lets us change rootnote et all
      if(!keyed) { 
        if( editMode == 0 ) { 
          rootNote = constrain( rootNote + dv, 0,120);
          droneMode = true;
        } else if( editMode == 1 ) { 
          scatterAmount = constrain( scatterAmount + dv, 0,50);
        } else if( editMode == 2 ) {
          filterAmount = constrain( filterAmount + dv, 0,190);
        } else if( editMode == 3 ) {
          volumeAmount = constrain( volumeAmount + dv, 0,15);
        }        
      }
    }
  }
  
  // ENCODER switch
  encoder_switch.update();
  if( encoder_switch.fell() ) {  // pressed
    bool keyed = false;
    for( int i=0; i<NUM_KEYS; i++ ) { 
      if( keys_pressed[i] ) {
        oscVals[i] = oscVals[i]==0 ? random(-MAX_TUNE,MAX_TUNE) : 0;
        keyed = true;
      }
    }
    if(!keyed) {
      editMode = (editMode + 1) % 4; // 4 = number of modes
      Serial.printf("editMode:%d drone:%d\n",editMode, droneMode);
    }
  }
  
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE, SH110X_BLACK); // white text, black background
//  display.setFont(&myfont);
//  display.setTextSize(2); // Draw 2X-scale text
  display.setFont(&myfont2);
  display.setTextSize(1);
  display.setCursor(0, 10);
  display.println(F("MPSP DRONE"));

  //display.setFont(0); // go back to built-in font
  display.setFont(&myfont2);
  display.setTextSize(1);

  display.setCursor(4,30);
  display.printf("scatter:%2d", scatterAmount);
  display.setCursor(4,40);
  display.printf("filter:%2d", filterAmount);
  display.setCursor(4,50);
  display.printf("volume:%2d", volumeAmount);
  display.setCursor(4,60);
  display.printf("root: %s%d", notenum_to_notestr(rootNote), notenum_to_oct(rootNote));

  if( editMode == 0 ) { 
    display.drawRect(0,52, 65,11, SH110X_WHITE);  // root note
  }
  else if( editMode == 1 ) { 
    display.drawRect(0,22, 65,11, SH110X_WHITE);  // scatter
  }
  else if( editMode == 2 ) { 
    display.drawRect(0,32, 65,11, SH110X_WHITE);  // filter
  }
  else if( editMode == 3 ) { 
    display.drawRect(0,42, 65,11, SH110X_WHITE);  // volume
  }

  display.setCursor(104,63);  display.print("oscs");
  display.drawRect(65,0, 62,58, SH110X_WHITE); // osc grid outline
  // draw which oscs are selected
  for( int i=0; i<NUM_KEYS; i++ ) {
    if( keys[i].read() == LOW ) { // == pressed (active low)
      display.drawRect(66 + 20*(i%3), 0 + 15*(i/3), 20,12, SH110X_WHITE);
    }
  }
  // draw osc grid values
  for( int i=0; i<NUM_KEYS/4; i++ ) {
    display.setCursor(60 + (i*20), 10);
    display.printf("%4d", oscVals[i + 0*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 25);
    display.printf("%4d", oscVals[i + 1*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 40);
    display.printf("%4d", oscVals[i + 2*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 55);
    display.printf("%4d", oscVals[i + 3*(NUM_KEYS/4)]);
  }
   
  display.display();

}
