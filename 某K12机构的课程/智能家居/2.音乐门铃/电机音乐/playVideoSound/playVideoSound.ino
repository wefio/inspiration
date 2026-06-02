// 基础节拍定义 (单位: ms)
int BEAT = 500; // 一拍的时长，可根据需要调快或调慢

// 定义 F 调频率
#define NOTE_L3 220  // 低音 3
#define NOTE_L5 262
#define NOTE_L6 294
#define NOTE_L7 330
#define NOTE_1  349
#define NOTE_2  392
#define NOTE_3  440
#define NOTE_4  466
#define NOTE_5  523
#define NOTE_6  587


void playLanHuaCao() {
  int pin = 3; // 蜂鸣器引脚

  // --- 第一段：我从山中来，带来兰花草 ---
  // 6 3 3 3 | 3. 2 | 1. 2 1 7̣ | 6̣ - 
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_3); delay(BEAT*0.5);

  tone(pin, NOTE_3); delay(BEAT*0.75);
  tone(pin, NOTE_2); delay(BEAT*0.25);

  tone(pin, NOTE_1); delay(BEAT*0.75);
  tone(pin, NOTE_2); delay(BEAT*0.25);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*2.0);

  // --- 第二段：种在小园中，希望花开早 ---
  // 6 6 6 6 | 6. 5 | 3 5 5 #4 | 3 -
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_6); delay(BEAT*0.5);

  tone(pin, NOTE_6); delay(BEAT*0.75);
  tone(pin, NOTE_5); delay(BEAT*0.25);

  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_5); delay(BEAT*0.5);
  tone(pin, NOTE_5); delay(BEAT*0.5);
  tone(pin, NOTE_4); delay(BEAT*0.5); // #4 在F调中接近 466Hz

  tone(pin, NOTE_3); delay(BEAT*2.0);

  // --- 第三段：一日看三回，看得花时过 ---
  // 3 6 6 5 | 3. 2 | 1. 2 1 7̣ | 6̣ 3
  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_6); delay(BEAT*0.5);
  tone(pin, NOTE_5); delay(BEAT*0.5);

  tone(pin, NOTE_3); delay(BEAT*0.75);
  tone(pin, NOTE_2); delay(BEAT*0.25);

  tone(pin, NOTE_1); delay(BEAT*0.75);
  tone(pin, NOTE_2); delay(BEAT*0.25);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*1.5);
  tone(pin, NOTE_3); delay(BEAT*0.5);

  // --- 第四段：兰花却依然，苞也无一个 ---
  // 3 1 1 7̣ | 6̣ 3 | 2 1 7̣ 5̣ | 6̣ -
  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*1.5);
  tone(pin, NOTE_3); delay(BEAT*0.5);

  tone(pin, NOTE_2); delay(BEAT*0.5);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);
  tone(pin, NOTE_L5); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*2.0);

  // --- 结尾间奏 ---
  // (3 1 1 7̣ | 6̣. 3̣ | 2 2 5̣ 7̣ | 6̣ -)
  tone(pin, NOTE_3); delay(BEAT*0.5);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_1); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*1.5);
  tone(pin, NOTE_L3); delay(BEAT*0.5); // 这里的3有下划线且有底点，是极低音

  tone(pin, NOTE_2); delay(BEAT*0.5);
  tone(pin, NOTE_2); delay(BEAT*0.5);
  tone(pin, NOTE_L5); delay(BEAT*0.5);
  tone(pin, NOTE_L7); delay(BEAT*0.5);

  tone(pin, NOTE_L6); delay(BEAT*2.0);
  
  noTone(pin); // 停止播放
}

void audio() {
  if (digitalRead(2) == 0) {
    playLanHuaCao();

  } else {
    noTone(3);

  }
}

void setup() {
  pinMode(3, OUTPUT);
}

void loop() {
  audio();

}
