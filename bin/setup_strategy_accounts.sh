#!/bin/bash
# Setup script to initialize separate account directories for each strategy
# Usage: ./bin/setup_strategy_accounts.sh <strategy_name>

STRATEGY_NAME=${1:-"default"}

echo "Setting up separate account directory for strategy: $STRATEGY_NAME"
echo ""

# Create conf directory structure
CONF_DIR="conf-$STRATEGY_NAME"
mkdir -p "$CONF_DIR"/{connectors,strategies,controllers,scripts}

# Copy base config files if they exist
if [ -f "conf/conf_client.yml" ]; then
    cp conf/conf_client.yml "$CONF_DIR/" 2>/dev/null || true
fi

if [ -f "conf/conf_fee_overrides.yml" ]; then
    cp conf/conf_fee_overrides.yml "$CONF_DIR/" 2>/dev/null || true
fi

if [ -f "conf/hummingbot_logs.yml" ]; then
    cp conf/hummingbot_logs.yml "$CONF_DIR/" 2>/dev/null || true
fi

# Copy encrypted connector configs if they exist
if [ -d "conf/connectors" ] && [ "$(ls -A conf/connectors)" ]; then
    echo "📋 Copying encrypted connector configs from conf/connectors/..."
    cp -r conf/connectors "$CONF_DIR/"
    echo "✅ Copied connector configs to $CONF_DIR/connectors/"
else
    echo "⚠️  No encrypted connectors found in conf/connectors/"
    echo "   Run './bin/hummingbot.py' first to create encrypted API key files"
fi

echo ""
echo "✅ Created directory structure: $CONF_DIR/"
echo ""
echo "Next steps:"
echo "1. If you haven't configured connectors yet:"
echo "   ./bin/hummingbot.py"
echo "   >>> connect binance"
echo "   >>> connect hyperliquid_perpetual"
echo "   >>> connect bybit"
echo "   >>> exit"
echo ""
echo "2. Re-run this script to copy new connector configs:"
echo "   ./bin/setup_strategy_accounts.sh $STRATEGY_NAME"
echo ""
echo "3. Set password in .env:"
echo "   ${STRATEGY_NAME^^}_CONFIG_PASSWORD=your_password"
echo ""

