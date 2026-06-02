void setup(){
  pinMode(4, INPUT);
  pinMode(9, OUTPUT);
}

void loop(){
  // 判断连接在4管脚的人体传感器是否感应到有人靠近，感应到则为1，否则为0.
  if (digitalRead(4) == 1) {
    // “高”表示点亮连接在9号管脚绿灯，时间延续5s
    digitalWrite(9,HIGH);
    delay(5000);
  } else {
    // “低”表示熄灭连接在9管脚绿灯
    digitalWrite(9,LOW);
  }
}
