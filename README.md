# Cat Health Control Bot

## Overview

**Cat Health Control Bot** is a Python-based Telegram bot designed to help cat owners track their pet's health. The bot allows users to log and monitor key health metrics, such as defecation events, stool types, asthma symptoms, and other relevant data, ensuring better care for their feline companions.

## Features

- **Health Tracking**: Log defecation events with stool type classification and asthma symptoms, including duration, reason, and inhalation usage.
- **Data Storage**: Persistent storage using MongoDB.
- **User-Friendly**: Simple and intuitive commands for easy interaction.
- **Web Interface**: Modern web application with authentication and mobile-responsive design.
- **Dockerized**: Fully containerized for seamless deployment.
- **Extensible**: Easily add new features or metrics to track.

## Dependencies

- **python-telegram-bot**: Telegram Bot API
- **pymongo**: MongoDB client for Python
- **flask**: Web framework for the web interface
- **werkzeug**: WSGI utilities (for password hashing)
- **Docker, Docker Compose**: For containerized deployment

## How It Works

1. **User** sends a command to log a health event (e.g., `/log_defecation` or `/log_asthma`).
2. **Bot** prompts the user for details, such as stool type or asthma symptoms (duration, reason, inhalation usage, and comments).
3. **Data** is stored in a MongoDB database.
4. **User** can retrieve logs or summaries using commands (e.g., `/get_logs`).

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Telegram Bot Token

### Installation & Run

1. Clone the repository:

   ```sh
   git clone <repo-url>
   cd cat-health-control
   ```

2. Create a `.env` file (example):

   ```env
   MONGO_USER=admin
   MONGO_PASS=password
   MONGO_HOST=db
   MONGO_PORT=27017
   MONGO_DB=cat_health
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   FLASK_SECRET_KEY=your-secret-key-for-sessions
   DEFAULT_PASSWORD=admin123
   ```

3. Start all services:

   ```sh
   docker-compose up -d --build
   ```

### Usage

#### Telegram Bot

- Use the bot's main menu to select actions:
  - **Asthma Attack**: Log an asthma attack by providing details such as duration and reason.
  - **Defecation**: Log a defecation event by selecting the stool type.
  - **Export Data**: View or export health logs in various formats (CSV, markdown, or message).
- Follow the bot's prompts to complete each action.
- Use the "Back to Menu" button to return to the main menu at any time.

#### Web Interface

1. Access the web interface at `http://localhost:5001`
2. Login with credentials:
   - Username: `admin`
   - Password: `admin123`
3. Use the dashboard to:
   - Record asthma attacks with full details
   - Record defecation events
   - View history of all recorded events
4. The interface is fully responsive and works on mobile devices

### Useful Commands

- Stop all services:

  ```sh
  docker-compose down
  ```

## Project Structure

```text
bot/
  db.py            # MongoDB database logic
  main.py          # Telegram bot logic
  whitelist.txt    # User whitelist
web/
  app.py           # Flask web application
  main.py          # Web app entry point
  templates/       # HTML templates
    base.html
    login.html
    dashboard.html
  static/          # Static files (CSS, JS)
    css/
      style.css
.env
docker-compose.yml
Dockerfile
README.md
requirements.txt
pyproject.toml
```

## Contributing

Pull requests and suggestions are welcome! Please open an issue or submit a PR to help improve the project.

## License

This project is licensed under the MIT License. See the [LICENSE](https://opensource.org/license/mit) file for details.
