#include "matrix_keyboard_v3.h"

#include "Servo.h"

volatile int index;
String key;
String passwd;
String keyStr;
Servo servo_12;

MatrixKeyboard myMatrixKeyboardV3(0x65);

void setup(){
  Serial.begin(9600);
  myMatrixKeyboardV3.Setup();

  index = 0;
  key = "";
  passwd = "123";
  keyStr = "";
  servo_12.attach(12);
}

void loop(){
  key = myMatrixKeyboardV3.GetTouchedKey();
  if (key != "") {
    Serial.println(key);
    delay(500);
    if (key == "#") {
      keyStr = "";

    } else {
      keyStr = String(keyStr) + String(key);
      index = index + 1;
      Serial.println(index);
      if (index == 3) {
        if (keyStr == passwd) {
          Serial.println("hello");
          keyStr = "";
          // 感应到人体，大门舵机开
          servo_12.write(90);
          delay(1000);

        } else {
          // 感应到人体，大门舵机开
          servo_12.write(180);
          delay(1000);

        }
        index = 0;
        keyStr = "";

      }

    }

  }

}