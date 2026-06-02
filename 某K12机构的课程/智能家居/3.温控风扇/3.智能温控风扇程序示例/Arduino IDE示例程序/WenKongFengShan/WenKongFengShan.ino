
#include "DHT.h"

DHT dhtA3(A3, 11);

void setup(){
  Serial.begin(9600);
   dhtA3.begin();
  pinMode(3, OUTPUT);
}

void loop(){
  // 使用串口监视器查看温度传感器的温度模拟值
  Serial.println(String("T:") + String(dhtA3.readTemperature()));
  delay(500);
  // 判断温度模拟值是否大于30，如果是，打开风扇；否则，关闭风扇
  if (dhtA3.readTemperature() > 30) {
    digitalWrite(3,HIGH);

  } else {
    digitalWrite(3,LOW);

  }

}