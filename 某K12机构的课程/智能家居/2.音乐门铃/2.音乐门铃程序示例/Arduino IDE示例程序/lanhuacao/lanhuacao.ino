void setup(){
  pinMode(2, INPUT);
  pinMode(3, OUTPUT);
}

void playNote(int note, int duration) {
  // 播放音符，然后停止一小段时间制造间隔
  if (note > 0) {
    tone(3, note);
    delay(duration);
    noTone(3);
    delay(30); // 音符之间的间隔时间
  } else {
    // 0表示休止符
    delay(duration);
  }
}

void loop(){
  // 判断连接在D2号接口的触摸传感器是否被触摸；0表示有触摸，1表示没有被触摸
  if (digitalRead(2) == 0) {
    // 《兰花草》经典旋律
    // "我从山中来，带着兰花草"
    playNote(392, 400);  // Sol (G4)
    playNote(440, 400);  // La (A4)
    playNote(494, 400);  // Si (B4)
    playNote(523, 400);  // Do (C5)
    playNote(587, 400);  // Re (D5)
    playNote(523, 400);  // Do (C5)
    playNote(494, 400);  // Si (B4)
    playNote(440, 800);  // La (A4) - 长音
    
    // "种在小园中，希望花开早"
    playNote(392, 400);  // Sol (G4)
    playNote(392, 400);  // Sol (G4)
    playNote(440, 400);  // La (A4)
    playNote(494, 400);  // Si (B4)
    playNote(523, 400);  // Do (C5)
    playNote(587, 400);  // Re (D5)
    playNote(659, 400);  // Mi (E5)
    playNote(587, 800);  // Re (D5) - 长音
    
    // "一日看三回，看得花时过"
    playNote(587, 400);  // Re (D5)
    playNote(659, 400);  // Mi (E5)
    playNote(587, 400);  // Re (D5)
    playNote(523, 400);  // Do (C5)
    playNote(494, 400);  // Si (B4)
    playNote(440, 400);  // La (A4)
    playNote(392, 400);  // Sol (G4)
    playNote(440, 400);  // La (A4)
    playNote(494, 400);  // Si (B4)
    playNote(523, 400);  // Do (C5)
    playNote(494, 400);  // Si (B4)
    playNote(440, 800);  // La (A4) - 长音
    
    // "兰花却依然，苞也无一个"
    playNote(392, 400);  // Sol (G4)
    playNote(392, 400);  // Sol (G4)
    playNote(440, 400);  // La (A4)
    playNote(494, 400);  // Si (B4)
    playNote(523, 400);  // Do (C5)
    playNote(587, 400);  // Re (D5)
    playNote(523, 400);  // Do (C5)
    playNote(494, 400);  // Si (B4)
    playNote(440, 400);  // La (A4)
    playNote(392, 800);  // Sol (G4) - 长音
    
    // 最后的结束音
    tone(3, 392);
    delay(1200);
    noTone(3);
    delay(300);
    
  } else {
    noTone(3);
  }
}
