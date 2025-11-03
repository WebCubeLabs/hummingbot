# Setup Procedures

## 1. Setup Account Directories
```bash
./bin/setup_strategy_accounts.sh pmm
./bin/setup_strategy_accounts.sh funding-arb
./bin/setup_strategy_accounts.sh rsi
```

## 2. Create .env File (Environment Variables)
```bash
cp env.template .env
# Edit .env and fill in:
# - CONFIG_PASSWORD (required, shared by all strategies)
# - API keys for each strategy
# - Optional: strategy-specific passwords (XXX_CONFIG_PASSWORD)
```

## 3. Run Locally (Without Docker)

```bash
# Load environment variables
export $(cat .env | xargs)

# Activate conda
conda activate hummingbot

# Run strategies
python3 bin/hummingbot_run.py --strategy v2_funding_rate_arb
python3 bin/hummingbot_run.py --strategy v2_directional_rsi
python3 bin/hummingbot_run.py --strategy simple_pmm
```

---

## 4. Build & Run (Docker)
```bash
docker-compose build
docker-compose up -d
```

## 5. Check Logs
```bash
docker-compose logs -f hummingbot-simple-pmm
docker-compose logs -f hummingbot-funding-arb
docker-compose logs -f hummingbot-directional-rsi
```

## 6. Stop Docker
```bash
docker-compose down
```

---

## Structure (No encrypted files needed!)
```
conf-pmm/               (Empty - uses env vars)
conf-funding-arb/       (Empty - uses env vars)
conf-rsi/               (Empty - uses env vars)

.env                    (All credentials here)
├── CONFIG_PASSWORD               (Required: shared password)
├── PMM_BINANCE_API_KEY          (Required per strategy)
├── FUNDING_ARB_BINANCE_API_KEY
├── RSI_BINANCE_API_KEY
└── TWAP_BINANCE_API_KEY
└── PMM_CONFIG_PASSWORD           (Optional: overrides shared)
```

---

## docker-compose.yml Format (Fallback Pattern)
```yaml
services:
  pmm-maker:
    environment:
      - STRATEGY_NAME=pmm
      - CONFIG_PASSWORD=${PMM_CONFIG_PASSWORD:-${CONFIG_PASSWORD}}  # Falls back to shared
      - BINANCE_API_KEY=${PMM_BINANCE_API_KEY}
      - BINANCE_API_SECRET=${PMM_BINANCE_API_SECRET}
      
  funding-arb:
    environment:
      - STRATEGY_NAME=funding-arb
      - CONFIG_PASSWORD=${FUNDING_ARB_CONFIG_PASSWORD:-${CONFIG_PASSWORD}}
      - BINANCE_API_KEY=${FUNDING_ARB_BINANCE_API_KEY}
      - BINANCE_API_SECRET=${FUNDING_ARB_BINANCE_API_SECRET}
      - HYPERLIQUID_PERPETUAL_API_KEY=${FUNDING_ARB_HYPERLIQUID_API_KEY}
      - HYPERLIQUID_PERPETUAL_API_SECRET=${FUNDING_ARB_HYPERLIQUID_API_SECRET}
      - BYBIT_API_KEY=${FUNDING_ARB_BYBIT_API_KEY}
      - BYBIT_API_SECRET=${FUNDING_ARB_BYBIT_API_SECRET}
```

---

## Railway Deployment

### Create Services
```bash
railway service create funding-arb
railway service create rsi-strategy
```

### Configure Service

**Start Command:**
```bash
conda activate hummingbot && python scripts/v2_funding_rate_arb.py
```

**Environment Variables:**
```bash
CONFIG_PASSWORD=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
HYPERLIQUID_PERPETUAL_API_KEY=0x_xxx
HYPERLIQUID_PERPETUAL_API_SECRET=0x_xxx
BYBIT_API_KEY=xxx
BYBIT_API_SECRET=xxx
```

