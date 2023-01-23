
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

const int NUM_KEYS = 12;
const int DW = 128;
const int DH = 64;

const int key_pins[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};

Bounce keys[NUM_KEYS];
Bounce encoder_switch;

Adafruit_NeoPixel leds = Adafruit_NeoPixel(NUM_KEYS, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);
Adafruit_SH1106G display = Adafruit_SH1106G(DW, DH, &SPI1, OLED_DC, OLED_RST, OLED_CS);

RotaryEncoder encoder(PIN_ROTB, PIN_ROTA, RotaryEncoder::LatchMode::FOUR3);
void checkEncoderPosition() {  encoder.tick(); } // just call tick() to check the state.

int encoder_pos = 0; // our encoder position state
bool keys_pressed[NUM_KEYS];
int edit_mode = 0; // 0 = gain, 1 = harmonics
uint32_t last_encoder_millis = 0;

// values used by Mozzi on core0
byte root_note = 48; // MIDI base note
int osc_vals[ NUM_KEYS ];
//

int notenum_to_oct(int notenum) {
  return (notenum / 12) - 2;
}

const char* notenum_to_notestr(int notenum) {
  const char* note_strs[] = { "C ", "C#", "D ", "D# ", "E ", "F ", "F#", "G ", "G#", "A ", "A#", "B ", "C "};
  return note_strs[ notenum % 12 ];
}

// core1 runs UI
void setup1() {
  Serial.begin(115200);
  delay(1000); // 
  
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
    osc_vals[i] = 50 + i;
  }
  
  Serial.println("dronetest");
}

void loop1() { 
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
      Serial.print("osc_vals: ");
      for(int i=0; i<NUM_KEYS; i++ ) { 
        Serial.print(osc_vals[i]); Serial.print(" ");
      }
      Serial.println();
    }    
  }
  leds.show();
  
  // ENCODER
  encoder_switch.update();
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
      bool keymode = false;
      for( int i=0; i<NUM_KEYS; i++ ) { 
        if( keys_pressed[i] ) { 
          osc_vals[i] = constrain(osc_vals[i] + dv, -99,99);
          keymode = true;
        }
      }
      // if no keys pressed, just turning knob lets us change rootnote
      if(!keymode) { 
        root_note = constrain( root_note + dv, 0,120);
      }
    }
  }
  
  if( encoder_switch.fell() ) {  // pressed
    for( int i=0; i<NUM_KEYS; i++ ) { 
      if( keys_pressed[i] ) {
        osc_vals[i] = osc_vals[i]==0 ? random(-99,99) : 0;
      }
    }
  }
  bool encoder_pressed = encoder_switch.read() == LOW;
  
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE, SH110X_BLACK); // white text, black background
//  display.setFont(&myfont);
//  display.setTextSize(2); // Draw 2X-scale text
  display.setFont(&myfont2);
  display.setTextSize(1);
  display.setCursor(0, 10);
  display.println(F("mpsp drone"));

  //display.setFont(0); // go back to built-in font
  display.setFont(&myfont2);
  display.setTextSize(1);

  display.setCursor(0,25);
  display.printf("root: %s%d", notenum_to_notestr(root_note), notenum_to_oct(root_note));
 
  for( int i=0; i<NUM_KEYS; i++ ) {
    if( keys[i].read() == LOW ) { // == pressed (active low)
      display.drawRect(65 + 20*(i%3), 0 + 15*(i/3), 20,15, SH110X_WHITE);
    }
  }
  for( int i=0; i<NUM_KEYS/4; i++ ) {
    display.setCursor(60 + (i*20), 10);
    display.printf("%4d", osc_vals[i + 0*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 25);
    display.printf("%4d", osc_vals[i + 1*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 40);
    display.printf("%4d", osc_vals[i + 2*(NUM_KEYS/4)]);
    display.setCursor(60 + (i*20), 55);
    display.printf("%4d", osc_vals[i + 3*(NUM_KEYS/4)]);
  }
  
  display.setCursor(110,15);
  display.print(encoder_pressed ? "@" : ".");
  
  display.display();

}
