# AiBot

## Description
AiBot is a Python-based AI-powered Telegram bot that interacts with users through chat. It leverages AI to generate responses and enhance user experience.

## Features
- AI-based chat responses
- Telegram bot integration
- Easy setup and deployment

## Installation
### Prerequisites
- Python (>=3.7)
- A Telegram bot token (Get from @BotFather on Telegram)

### Steps
1. **Clone the repository**
   ```bash
   git clone https://github.com/prince-cyb/AiBot.git
   cd AiBot
   ```
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up API keys and configuration**
   - Create a `.env` file or a `config.json` file in the root directory.
   - Add the required API keys (Example format):
     ```env
     TELEGRAM_BOT_TOKEN=your_telegram_token
     GEMINI_API_KEY=your_geminiai_api_key  # If using GEMINIAI for AI responses
     ```
4. **Run the bot**
   ```bash
   python bot.py
   ```

## Usage
- Start a chat with your Telegram bot.
- The bot will respond based on AI-generated text.

## Contribution
Feel free to fork the repository and create pull requests for improvements.

## License
This project is licensed under [MIT License](LICENSE).

