# NewsFlow-Bot
It receives RSS information from various media and magazines and pushes it to you after appropriate translation.
NewsFlow-Bot is a powerful Discord bot that fetches news from various RSS feeds, translates them, and posts them to specified Discord channels. Future plans include creating bots for the Telegram platform and an email newsletter-based bot.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Contributing](#contributing)
- [License](#license)
- [Author](#author)

## Installation

Follow these steps to install the project:

1. Clone the repository:
    ```bash
    git clone https://github.com/your-username/NewsFlow-Bot.git
    ```
2. Install dependencies:
    ```bash
    cd NewsFlow-Bot
    pip install -r requirements.txt
    ```

3. Create a `.env` file and add the following content:
    ```plaintext
    GOOGLE_TRANSLATE_API_KEY=your_google_translate_api_key
    DEEPL_API_KEY=your_deepl_api_key
    DISCORD_TOKEN=your_discord_token
    ```

## Usage

Follow these steps to use the project:

1. Start the project:
    ```bash
    python full_rss_Discord_Bot.py
    ```
2. Add your Discord Bot to the server and configure the appropriate channel and RSS feeds.

## Commands

- `!add_rss <rss_url>`: Add a new RSS feed.
- `!remove_rss <rss_url>`: Remove an existing RSS feed.
- `!set_channel <channel>`: Set the target channel for message delivery.
- `!list_rss`: List all currently configured RSS feeds.
- `!set_language <language>`: Set the target language for translation.
- `!set_interval <interval>`: Set the interval for checking RSS feeds (in minutes).

## Contributing

Any form of contribution is welcome! Follow these steps to contribute:

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

- **Your Name** - *Initial work* - [YourGitHubProfile](https://github.com/your-username)

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## Screenshots

![Project Screenshot](path/to/screenshot.png)

![Demo GIF](path/to/demo.gif)

