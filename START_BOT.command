#!/bin/bash
# VaniHealthBot — Double-click this file to install and run your bot!

# Move to the folder this script is in
cd "$(dirname "$0")"

echo ""
echo "🌸 VaniHealthBot Setup & Launch"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 not found. Install it from https://python.org then try again."
    read -p "Press Enter to close..."
    exit 1
fi

echo "✅ Python3 found: $(python3 --version)"
echo ""
echo "📦 Installing dependencies..."
pip3 install python-telegram-bot==20.7 anthropic python-dotenv gspread google-auth --quiet

echo ""
echo "✅ Dependencies installed!"
echo ""
echo "🚀 Starting VaniHealthBot..."
echo "----------------------------"
echo "Open Telegram and message @VaniHealthBot to get started!"
echo "Press Ctrl+C to stop the bot."
echo ""

python3 main.py
