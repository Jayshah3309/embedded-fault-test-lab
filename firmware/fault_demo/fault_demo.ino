#include "control.h"

// UNO demo: permission indicator ONLY. No motor, relay or mains load.
faultlab::Controller controller;
uint32_t lastSample=0,lastReport=0;
bool firstSample=true;

void setup() {
  pinMode(LED_BUILTIN,OUTPUT); digitalWrite(LED_BUILTIN,LOW);
  pinMode(2,INPUT_PULLUP); // normally closed stop loop to GND
  pinMode(3,INPUT_PULLUP); // sample-valid jumper to GND; unplug to inject invalid
  Serial.begin(115200);
  Serial.println(F("Fault Lab UNO demo; send H heartbeat, R reset, A arm, X stop"));
}

void loop() {
  uint32_t now=millis();
  char command='-';
  // Process at most one non-whitespace command per loop; never block awaiting Serial.
  if (Serial.available()) {
    char c=char(Serial.read());
    if(c!='\r' && c!='\n' && c!=' ' && c!='\t') command=c;
  }
  bool fresh=firstSample || uint32_t(now-lastSample)>=100;
  if(fresh) { firstSample=false; lastSample=now; }
  faultlab::Input input={fresh,digitalRead(3)==LOW,int16_t(fresh?analogRead(A0):0),digitalRead(2)==LOW,command};
  controller.update(now,input);
  digitalWrite(LED_BUILTIN,controller.permit()?HIGH:LOW);
  if(uint32_t(now-lastReport)>=100) {
    lastReport=now;
    Serial.print(now); Serial.print(','); Serial.print(faultlab::stateName(controller.state()));
    Serial.print(','); Serial.print(controller.permit()?1:0); Serial.print(',');
    Serial.println(controller.faults());
  }
}
