# Telegram Bot with Ollama

This repository contains a minimal Telegram bot that uses [Ollama](https://github.com/jmorganca/ollama) (Local Large Language Model runner) to answer questions. The bot sends user queries to the Ollama HTTP API and returns the responses to Telegram.

## Features
- Text-based conversation with the LLM via Telegram.
- Simple code structure for easy customization.

---

## Prerequisites

1. **Python 3.9+** recommended.
2. **Telegram Bot Token**:
   - Obtain a token from [BotFather](https://t.me/BotFather) on Telegram.
   - Store it in the `TELEGRAM_BOT_TOKEN` environment variable, or set it manually in `bot.py` (not recommended for production).

3. **Ollama**:
   - Installed and running locally, or accessible via Docker.
   - By default, the bot expects Ollama at `http://localhost:11411/generate`.
   - If different, set the environment variable `OLLAMA_API_URL`.
