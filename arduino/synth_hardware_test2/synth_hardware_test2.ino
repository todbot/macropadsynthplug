/**
 * synth_hardware_test2.ino  -- simple hardware test in Arduino for MacroPad RP2040
 * 15 Dec 2022 - @todbot / Tod Kurt
 * Part of https://github.com/todbot/macropadsynthplug/
 * 
 * Must edit Mozzi library!
 * - in "Mozzi/AudioConfigRP2040.h"
 *   - change to "AUDIO_CHANNEL_1_PIN 20"
 *   
 **/
 
#include <Wire.h>
#include <RotaryEncoder.h>
#include <Bounce2.h>
#include <Adafruit_NeoPixel.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <Fonts/FreeMono9pt7b.h>
#include <Fonts/FreeMono12pt7b.h>
#include <Fonts/FreeMono18pt7b.h>
#include <Fonts/FreeMonoBold12pt7b.h>
#include "Font5x7FixedMono.h"
#define myfont FreeMono9pt7b
#define myfont2 Font5x7FixedMono 
// see: https://learn.adafruit.com/adafruit-gfx-graphics-library/using-fonts

#include <MozziGuts.h>
#include <Oscil.h>
#include <tables/square_no_alias512_int8.h> // oscillator waveform
#include <tables/saw_analogue512_int8.h> // oscillator waveform
#include <mozzi_rand.h>  // for rand()
#include <mozzi_midi.h>  // for mtof()

//Oscil<SAW_ANALOGUE512_NUM_CELLS, AUDIO_RATE> aOsc(SAW_ANALOGUE512_DATA);
Oscil<SQUARE_NO_ALIAS512_NUM_CELLS, AUDIO_RATE> aOsc(SQUARE_NO_ALIAS512_DATA);
uint16_t note_duration = 100;
uint32_t lastMillis = 0;

/// 
const int num_keys = 12;
const int dw = 128;
const int dh = 64;

const int key_pins[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12};

Adafruit_NeoPixel leds = Adafruit_NeoPixel(num_keys, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

Bounce keys[num_keys];
Bounce encoder_switch;

RotaryEncoder encoder(PIN_ROTA, PIN_ROTB, RotaryEncoder::LatchMode::FOUR3);
void checkEncoderPosition() {  encoder.tick(); } // just call tick() to check the state.
int encoder_pos = 0; // our encoder position state

Adafruit_SH1106G display = Adafruit_SH1106G(dw, dh, &SPI1, OLED_DC, OLED_RST, OLED_CS);


void setup() {
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

  // Mozzi setup
  //Mozzi.setPin(0,1);   // GP01
  //Mozzi.setPin(0,29);  // this sets RP2040 GP29  // QT Py A0 
  //Mozzi.setPin(0,21);  // this sets RP2040 GP21, aka MacroPad RP2040 StemmaQT SCL
  startMozzi();
  Serial.println("hello!");
}

char keyspressed_str[num_keys+1];

void loopblah()
{
  // KEYS
  for (uint8_t i=0; i< num_keys; i++) {
    keys[i].update();
    bool keypressed = keys[i].read() == LOW; // active low
    keyspressed_str[i] = keypressed ? '1' : '0';
//    digitalWrite( led_pins[i], keypressed); // light up the key LEDs for yucks
    leds.setPixelColor(i, keypressed ? 0x0000ff : 0x110000);
    if(keypressed) { 
      Serial.printf("key %d pressed!\n", i);
    }
  }
  leds.show();
  
  // ENCODER
  encoder_switch.update();
  encoder.tick();
  int newPos = encoder.getPosition();
  if (encoder_pos != newPos) {
    Serial.print("Encoder:");
    Serial.print(newPos);
    Serial.print(" Direction:");
    Serial.println((int)(encoder.getDirection()));
    encoder_pos = newPos;
  }
  bool encoder_pressed = encoder_switch.read() == LOW;
 
  display.clearDisplay();
  display.setFont(&myfont);
  display.setCursor(0, 10);
//  display.setTextSize(2); // Draw 2X-scale text
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE, SH110X_BLACK); // white text, black background
  display.println(F("hello world"));

  //display.setFont(0); // go back to built-in font
  display.setFont(&myfont2);
  display.setTextSize(1);
  display.setCursor(0,45);
  display.print("enc:");
  display.setCursor(50, 45);
  display.print(encoder_pos);
  display.setCursor(110, 45);
  display.print(encoder_pressed ? "*" : ".");

  display.setCursor(0, 60);
  display.print("key:");
  display.setCursor(50, 60);
  display.print(keyspressed_str);
  display.display();
  
}

// core0 just does audio stuff
void loop() { 
  audioHook();
}
  
// mozzi function, called every CONTROL_RATE
void updateControl() {
    
  if( millis() - lastMillis > note_duration )  {
    lastMillis = millis();
    float f = mtof( rand(36,60) );
    aOsc.setFreq( f ); 
    Serial.printf("new note: %f\n", f);
  }
}

// mozzi function, called every AUDIO_RATE to output sample
AudioOutput_t updateAudio() {
  int16_t asig = (long) 0;
  asig += aOsc.next();
  return MonoOutput::from8Bit(asig);
}
