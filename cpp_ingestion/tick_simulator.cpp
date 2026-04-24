#include <random>
#include <vector>
#include <string>
#include <chrono>
#include <cmath>
#include <unordered_map>
#include "tick.h"

class TickSimulator {
private:
    std::vector<std::string> symbols;
    std::unordered_map<std::string, double> current_prices;
    std::unordered_map<std::string, double> bid_prices;
    std::unordered_map<std::string, double> ask_prices;
    std::mt19937_64 rng;
    std::normal_distribution<double> price_change_dist;
    std::uniform_int_distribution<uint64_t> volume_dist;
    std::uniform_real_distribution<double> spread_dist;
    std::uniform_real_distribution<double> spike_dist;

public:
    TickSimulator(unsigned int seed = 42) 
        : rng(seed), 
          price_change_dist(0.0, 0.001),  // mean=0, sigma=0.001 for realistic drift
          volume_dist(100, 10000),         // volume between 100 and 10,000
          spread_dist(0.01, 0.10),         // spread between 0.01 and 0.10
          spike_dist(0.0, 1.0)             // for volume spike detection
    {
        initialize_symbols();
        initialize_prices();
    }

    void initialize_symbols() {
        // Simulate 100 realistic stock symbols
        symbols = {
            "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "BRK.B", "JNJ", "V", "WMT", "PG",
            "MA", "HD", "NFLX", "DIS", "BA", "IBM", "INTC", "AMD", "COIN", "NVDA",
            "CRM", "ADBE", "ACN", "CSCO", "ORCL", "QCOM", "TXN", "AVGO", "NXPI", "MU",
            "PYPL", "SQ", "TTD", "NET", "CRWD", "OKTA", "ZS", "SNPS", "CDNS", "MCHP",
            "ASML", "AMAT", "LRCX", "KLA", "ONTO", "MRVL", "MSTR", "RIOT", "MARA", "CLSK",
            "GOOG", "FB", "TWTR", "SNAP", "PIN", "PINS", "SHOP", "ETSY", "FTCH", "DASH",
            "UBER", "LYFT", "RBLX", "U", "PTON", "ZILLOW", "ABNB", "LCID", "RIVN", "NIO",
            "XPev", "LI", "BIDU", "PDD", "SE", "DDOG", "SNOW", "ZM", "MDB", "DBX",
            "BOX", "NEWR", "LMND", "HUBS", "S", "FSLY", "SUMO", "REGI", "TREX", "PLYA",
            "KMTB", "EXLS", "VRSN", "JKHY", "JBHT", "CHRW", "XPO", "J", "UTL", "YUM"
        };
    }

    void initialize_prices() {
        // Initialize prices with realistic starting values
        for (const auto& symbol : symbols) {
            double base_price = 100.0 + (std::hash<std::string>()(symbol) % 400);
            current_prices[symbol] = base_price;
            bid_prices[symbol] = base_price - 0.05;
            ask_prices[symbol] = base_price + 0.05;
        }
    }

    Tick generate_tick() {
        // Select a random symbol
        std::uniform_int_distribution<size_t> symbol_dist(0, symbols.size() - 1);
        const std::string& symbol = symbols[symbol_dist(rng)];

        // Random walk price movement
        double price_change = price_change_dist(rng);
        double new_price = current_prices[symbol] * (1.0 + price_change);
        
        // Ensure price stays positive and realistic
        if (new_price <= 0) new_price = current_prices[symbol];
        current_prices[symbol] = new_price;

        // Update bid/ask with realistic spread
        double spread = spread_dist(rng);
        // Ensure spread is always positive: bid < mid < ask
        bid_prices[symbol] = new_price - spread / 2.0;
        ask_prices[symbol] = new_price + spread / 2.0;
        
        // Safety check: ensure bid < ask
        if (bid_prices[symbol] >= ask_prices[symbol]) {
            bid_prices[symbol] = new_price - 0.01;
            ask_prices[symbol] = new_price + 0.01;
        }

        // Generate volume (occasionally spike)
        uint64_t volume;
        if (spike_dist(rng) > 0.95) {  // 5% chance of volume spike
            volume = volume_dist(rng) * 5;  // 5x normal volume
        } else {
            volume = volume_dist(rng);
        }

        // Get current timestamp in nanoseconds
        auto now = std::chrono::system_clock::now();
        auto count = now.time_since_epoch().count();
        uint64_t timestamp = static_cast<uint64_t>(count);

        return {symbol, new_price, volume, bid_prices[symbol], ask_prices[symbol], timestamp};
    }

    const std::vector<std::string>& get_symbols() const {
        return symbols;
    }

    double get_current_price(const std::string& symbol) const {
        auto it = current_prices.find(symbol);
        if (it != current_prices.end()) {
            return it->second;
        }
        return 0.0;
    }
};
