#include "tick_simulator.cpp"
#include "zmq_publisher.cpp"

#include <iostream>
#include <thread>
#include <chrono>
#include <atomic>
#include <signal.h>
#include <iomanip>

// Global flag for clean shutdown
std::atomic<bool> should_exit(false);

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        std::cout << "\n[INGESTION] Received shutdown signal, exiting gracefully..." << std::endl;
        should_exit = true;
    }
}

int main() {
    // Register signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    std::cout << "=== HFT-Style Watchlist: C++ Ingestion Engine ===" << std::endl;
    std::cout << "[INGESTION] Starting tick simulator and publisher..." << std::endl;

    try {
        // Initialize simulator and publisher
        TickSimulator simulator;
        ZeroMQPublisher publisher;

        // Give subscriber time to connect
        std::cout << "[INGESTION] Waiting for subscriber connections (2 seconds)..." << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(2));

        std::cout << "[INGESTION] Publishing ticks at ~500/sec..." << std::endl;
        std::cout << "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" << std::endl;

        uint64_t tick_count = 0;
        auto start_time = std::chrono::high_resolution_clock::now();

        while (!should_exit) {
            // Generate and publish a tick
            Tick tick = simulator.generate_tick();
            publisher.publish_tick(tick);
            tick_count++;

            // Print status every 5000 ticks
            if (tick_count % 5000 == 0) {
                auto now = std::chrono::high_resolution_clock::now();
                auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - start_time).count();
                double rate = static_cast<double>(tick_count) / std::max(1L, elapsed);
                uint64_t discarded = publisher.get_ticks_discarded();
                size_t symbols = publisher.get_symbols_tracked();
                std::cout << "[INGESTION] Published " << tick_count << " ticks (~" 
                          << std::fixed << std::setprecision(0) << rate << " ticks/sec) | "
                          << "Tracking: " << symbols << " symbols | "
                          << "Discarded: " << discarded << " (validation)" << std::endl;
            }

            // Simulate real-time streaming: ~500 ticks per second
            std::this_thread::sleep_for(std::chrono::microseconds(2000));  // 2ms = 500 ticks/sec
        }

        std::cout << "\n[INGESTION] Graceful shutdown. Total ticks published: " << tick_count 
                  << " | Discarded: " << publisher.get_ticks_discarded() 
                  << " | Symbols tracked: " << publisher.get_symbols_tracked() << std::endl;
        return 0;

    } catch (const std::exception& e) {
        std::cerr << "[INGESTION ERROR] " << e.what() << std::endl;
        return 1;
    }
}
