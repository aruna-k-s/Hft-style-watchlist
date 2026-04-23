#include <zmq.hpp>
#include <string>
#include <cstring>
#include <iostream>
#include <stdexcept>

struct Tick {
    std::string symbol;
    double price;
    uint64_t volume;
    double bid;
    double ask;
    uint64_t timestamp;
};

class ZeroMQPublisher {
private:
    zmq::context_t context;
    zmq::socket_t socket;
    std::unordered_map<std::string, uint64_t> latest_timestamp;  // Latest tick per symbol for validation
    uint64_t ticks_discarded = 0;  // Count of discarded ticks
    static constexpr const char* ENDPOINT = "tcp://*:5555";
    bool is_running;

public:
    ZeroMQPublisher() 
        : context(1), 
          socket(context, zmq::socket_type::pub),
          is_running(false)
    {
        try {
            socket.bind(ENDPOINT);
            is_running = true;
            std::cout << "ZeroMQ Publisher bound to " << ENDPOINT << std::endl;
        } catch (const zmq::error_t& e) {
            std::cerr << "Failed to bind ZeroMQ socket: " << e.what() << std::endl;
            throw;
        }
    }

    ~ZeroMQPublisher() {
        try {
            if (is_running) {
                socket.close();
                is_running = false;
            }
        } catch (...) {
            // Suppress exceptions in destructor
        }
    }

    void publish_tick(const Tick& tick) {
        if (!is_running) {
            throw std::runtime_error("ZeroMQ Publisher is not running");
        }

        // VALIDATION: Discard stale ticks (older timestamps)
        if (latest_timestamp.count(tick.symbol) > 0) {
            if (tick.timestamp <= latest_timestamp[tick.symbol]) {
                // Stale or duplicate tick detected - discard silently
                ticks_discarded++;
                return;
            }
        }

        // VALIDATION: Check bid < ask (valid spread)
        if (tick.bid >= tick.ask) {
            // Invalid quote - discard
            ticks_discarded++;
            return;
        }

        // VALIDATION: Check price > 0
        if (tick.price <= 0) {
            ticks_discarded++;
            return;
        }

        // VALIDATION: Check volume > 0
        if (tick.volume <= 0) {
            ticks_discarded++;
            return;
        }

        // Update latest timestamp for this symbol
        latest_timestamp[tick.symbol] = tick.timestamp;

        // Serialize tick to binary format
        // Format: symbol_len(1) | symbol | price(8) | volume(8) | bid(8) | ask(8) | timestamp(8)
        std::string message;
        
        // Add symbol length and symbol
        uint8_t symbol_len = static_cast<uint8_t>(tick.symbol.length());
        message.push_back(symbol_len);
        message.append(tick.symbol);

        // Add numeric fields as binary
        message.append(reinterpret_cast<const char*>(&tick.price), sizeof(tick.price));
        message.append(reinterpret_cast<const char*>(&tick.volume), sizeof(tick.volume));
        message.append(reinterpret_cast<const char*>(&tick.bid), sizeof(tick.bid));
        message.append(reinterpret_cast<const char*>(&tick.ask), sizeof(tick.ask));
        message.append(reinterpret_cast<const char*>(&tick.timestamp), sizeof(tick.timestamp));

        try {
            zmq::message_t zmq_msg(message.begin(), message.end());
            socket.send(zmq_msg, zmq::send_flags::none);
        } catch (const zmq::error_t& e) {
            std::cerr << "Failed to publish tick: " << e.what() << std::endl;
            throw;
        }
    }

    // Lightweight buffer flush if needed
    void flush() {
        // ZeroMQ handles buffering automatically
    }

    bool is_connected() const {
        return is_running;
    }

    uint64_t get_ticks_discarded() const {
        return ticks_discarded;
    }

    size_t get_symbols_tracked() const {
        return latest_timestamp.size();
    }
};
