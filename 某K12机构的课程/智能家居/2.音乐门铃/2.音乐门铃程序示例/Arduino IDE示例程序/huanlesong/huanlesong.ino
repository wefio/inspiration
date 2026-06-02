void setup(){
  pinMode(2, INPUT);
  pinMode(3, OUTPUT);
}

void playNote(int note, int duration) {
  // 播放音符，然后停止一小段时间制造间隔
  tone(3, note);
  delay(duration);
  noTone(3);
  delay(50); // 音符之间的间隔时间
}

void loop(){
  // 判断连接在D2号接口的触摸传感器是否被触摸；0表示有触摸，1表示没有被触摸
  if (digitalRead(2) == 0) {
    // 欢乐颂旋律
    playNote(392, 500);  // G4 (Sol)
    playNote(392, 500);  // G4 (Sol)
    playNote(440, 500);  // A4 (La)
    playNote(494, 500);  // B4 (Si)
    playNote(494, 500);  // B4 (Si)
    playNote(440, 500);  // A4 (La)
    playNote(392, 500);  // G4 (Sol)
    playNote(349, 500);  // F4 (Fa)
    playNote(330, 500);  // E4 (Mi)
    playNote(330, 500);  // E4 (Mi)
    playNote(349, 500);  // F4 (Fa)
    playNote(392, 500);  // G4 (Sol)
    playNote(392, 400);  // G4 (Sol) - 稍短
    playNote(349, 200);  // F4 (Fa) - 更短
    tone(3, 349);        // F4 (Fa) - 长音
    delay(800);
    noTone(3);
    delay(200);          // 最后的长间隔
    
  } else {
    noTone(3);
  }
}
