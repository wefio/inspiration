
#include "Servo.h"

Servo servo_12;

void setup(){
  pinMode(7, INPUT);
  servo_12.attach(12);
}

void loop(){
  // 是否感应到车，“0”代表感应到，“1”代表没有感应到
  if (digitalRead(7) == 0) {
    servo_12.write(90);
    delay(1000);

  } else {
    servo_12.write(0);
    delay(1000);

  }

}