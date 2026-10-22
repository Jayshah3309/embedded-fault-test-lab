#pragma once
#include <stdint.h>

// Portable educational supervisor. This is not a certified safety controller.
namespace faultlab {
constexpr uint32_t SENSOR_TIMEOUT_MS = 500;
constexpr uint32_t HEARTBEAT_TIMEOUT_MS = 300;
constexpr int16_t TRIP_VALUE = 800;
constexpr int16_t RECOVERY_VALUE = 700;
enum Fault : uint16_t { SENSOR_INVALID=1, RANGE=2, STALE=4, HEARTBEAT=8,
                       OVER_LIMIT=16, STOP_OPEN=32, BAD_COMMAND=64, CLOCK=128 };
enum State : uint8_t { BOOT, READY, ACTIVE, STOPPED, FAULT };
struct Input { bool fresh; bool valid; int16_t value; bool stopClosed; char command; };
inline uint32_t age(uint32_t now, uint32_t then) { return uint32_t(now-then); }
inline const char* stateName(State s) {
  switch(s) {
    case BOOT: return "BOOT"; case READY: return "READY";
    case ACTIVE: return "ACTIVE"; case STOPPED: return "STOPPED";
    default: return "FAULT";
  }
}

class Controller {
  State state_ = BOOT;
  uint16_t faults_ = 0;
  uint32_t lastTick_ = 0, lastSample_ = 0, lastHeartbeat_ = 0;
  bool started_ = false, hasSample_ = false, hasHeartbeat_ = false;
  int16_t value_ = 0;
  uint8_t healthy_ = 0;
public:
  State state() const { return state_; }
  uint16_t faults() const { return faults_; }
  uint8_t healthySamples() const { return healthy_; }
  bool permit() const { return state_ == ACTIVE && faults_ == 0; }
  void update(uint32_t now, const Input& in) {
    if (!started_) { started_=true; lastTick_=lastSample_=now; }
    if (age(now,lastTick_) > 0x7FFFFFFFUL) {
      faults_ |= CLOCK; state_=FAULT; healthy_=0; lastTick_=now; return;
    }
    lastTick_=now;
    // Check existing data/heartbeat deadlines BEFORE accepting late replacements.
    if (age(now,lastSample_) >= SENSOR_TIMEOUT_MS) {
      faults_ |= STALE; healthy_=0;
    }
    if (state_ == ACTIVE && (!hasHeartbeat_ || age(now,lastHeartbeat_) >= HEARTBEAT_TIMEOUT_MS))
      faults_ |= HEARTBEAT;
    if (in.fresh) {
      if (!in.valid) { faults_ |= SENSOR_INVALID; healthy_=0; }
      else if (in.value < 0 || in.value > 1000) { faults_ |= RANGE; healthy_=0; }
      else {
        value_=in.value; hasSample_=true; lastSample_=now;
        if (value_ >= TRIP_VALUE) { faults_ |= OVER_LIMIT; healthy_=0; }
        else if (value_ <= RECOVERY_VALUE) { if (healthy_<3) healthy_++; }
        else healthy_=0;
      }
    }
    if (!in.stopClosed) { faults_ |= STOP_OPEN; healthy_=0; }
    const char command=in.command;
    if (command=='H') { hasHeartbeat_=true; lastHeartbeat_=now; }
    else if (command!='-' && command!='A' && command!='R' && command!='X') faults_ |= BAD_COMMAND;
    if (faults_) state_=FAULT;
    if (command=='X') { state_=faults_ ? FAULT : STOPPED; return; }
    const bool healthy = in.stopClosed && hasSample_ && healthy_>=3 &&
      value_<=RECOVERY_VALUE && age(now,lastSample_)<SENSOR_TIMEOUT_MS;
    const bool heartbeatFresh = hasHeartbeat_ && age(now,lastHeartbeat_)<HEARTBEAT_TIMEOUT_MS;
    if (command=='R' && healthy && heartbeatFresh) {
      faults_=0; state_=READY; // Explicit reset disarms. A separate A is mandatory.
    } else if (command=='A' && state_==READY && healthy && heartbeatFresh && !faults_) {
      state_=ACTIVE;
    }
  }
};
} // namespace faultlab
