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

const int num_keys = 12;
const int dw = 128;
const int dh = 64;

const int key_pins[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};

Adafruit_NeoPixel leds = Adafruit_NeoPixel(num_keys, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

Bounce keys[num_keys];
Bounce encoder_switch;
char keyspressed_str[] = "000000000000";

RotaryEncoder encoder(PIN_ROTB, PIN_ROTA, RotaryEncoder::LatchMode::FOUR3);
void checkEncoderPosition() {  encoder.tick(); } // just call tick() to check the state.
int encoder_pos = 0; // our encoder position state

Adafruit_SH1106G display = Adafruit_SH1106G(dw, dh, &SPI1, OLED_DC, OLED_RST, OLED_CS);
int last_key = 0;
int edit_mode = 0; // 0 = gain, 1 = harmonics

// core1 runs UI
void setup1() {
  Serial.begin(115200);

  // KEYS
  for (uint8_t i=0; i< num_keys; i++) {
    keys[i].attach( key_pins[i], INPUT_PULLUP);
  }

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

  // OLED
  display.begin(0, true); // we dont use the i2c address but we will reset!
  //display.clearDisplay();
  display.display();  // must clear before display, otherwise shows adafruit logo
  delay(1000);

  Serial.println("synth_additive_vco!");
}

void loop1() { 
  // KEYS
  for (uint8_t i=0; i< num_keys; i++) {
    keys[i].update();
    if(keys[i].fell() ) {  // active low
      keyspressed_str[i] = '1';
      last_key = i;
      Serial.printf("key %d pressed!\n", i);
      leds.setPixelColor(i, 0x0000ff);
    }
    if(keys[i].rose()) { // release
      keyspressed_str[i] = '0';
      leds.setPixelColor(i, 0x0000ff);
      leds.setPixelColor(i, 0x111111);
    }    
  }
  leds.show();
  
  // ENCODER
  encoder_switch.update();
  encoder.tick();
  int newPos = encoder.getPosition();
  if (encoder_pos != newPos) {
    Serial.print("gain: "); Serial.print(gain); Serial.print(" harm:"); Serial.println(harm_knob);
    if(edit_mode == 0 ) { 
      gain_knob += (newPos - encoder_pos)*2;
    } else if( edit_mode == 1 ) { 
      harm_knob += (newPos - encoder_pos)*2;
    }
    encoder_pos = newPos;
  }
  bool encoder_pressed = encoder_switch.read() == LOW;
  if( encoder_switch.fell() ) {  // pressed
    edit_mode = (edit_mode+1) % 2; 
  }
 
  display.clearDisplay();
  display.setFont(&myfont);
  display.setCursor(0, 10);
//  display.setTextSize(2); // Draw 2X-scale text
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE, SH110X_BLACK); // white text, black background
  display.println(F("synthplug    additivevco"));

  //display.setFont(0); // go back to built-in font
  display.setFont(&myfont2);
  display.setTextSize(1);
  display.setCursor(0,  45);  display.print("gain:");
  display.setCursor(30, 45);  display.print(gain_knob);
  display.setCursor(60, 45);  display.print("harm:");
  display.setCursor(90, 45);  display.print(harm_knob);
  display.setCursor(110,45);
  display.print(encoder_pressed ? "*" : ".");

  display.setCursor(0, 60);
  display.print("key:");
  display.setCursor(50, 60);
  display.print(keyspressed_str);
  display.display();
}
