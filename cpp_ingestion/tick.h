#pragma once

#include <string>
#include <cstdint>

struct Tick {
    std::string symbol;
    double price;
    uint64_t volume;
    double bid;
    double ask;
    uint64_t timestamp;
};