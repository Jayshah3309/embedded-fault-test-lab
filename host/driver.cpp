#include <iostream>
#include <sstream>
#include <string>
#include <limits>
#include "control.h"

// One strict whitespace-delimited frame per line: time fresh valid value stop command.
// Parse errors are a failing host run, never an implicit successful control step.
int main() {
  faultlab::Controller controller;
  std::string line;
  while (std::getline(std::cin,line)) {
    std::istringstream input(line);
    unsigned long long now;
    int fresh, valid, value, stop;
    std::string command, extra;
    if (!(input>>now>>fresh>>valid>>value>>stop>>command) || (input>>extra) ||
        now>std::numeric_limits<uint32_t>::max() ||
        (fresh!=0 && fresh!=1) || (valid!=0 && valid!=1) || (stop!=0 && stop!=1) ||
        value<std::numeric_limits<int16_t>::min() || value>std::numeric_limits<int16_t>::max() ||
        command.size()!=1) {
      std::cerr<<"invalid input frame\n"; return 2;
    }
    const faultlab::Input frame={fresh!=0,valid!=0,int16_t(value),stop!=0,command[0]};
    controller.update(uint32_t(now),frame);
    std::cout<<"{\"time_ms\":"<<now<<",\"state\":\""<<faultlab::stateName(controller.state())
      <<"\",\"permit\":"<<(controller.permit()?"true":"false")
      <<",\"faults\":"<<controller.faults()
      <<",\"healthy_samples\":"<<unsigned(controller.healthySamples())<<"}\n";
  }
  return std::cin.bad() ? 2 : 0;
}
