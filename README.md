# Cat Health Control Bot

## Overview

**Cat Health Control Bot** is a Python-based Telegram bot designed to help cat owners track their pet's health. The bot allows users to log and monitor key health metrics, such as defecation events, stool types, asthma symptoms, and other relevant data, ensuring better care for their feline companions.

## Features

- **Health Tracking**: Log defecation events with stool type classification and asthma symptoms, including duration, reason, and inhalation usage.
- **Data Storage**: Persistent storage using PostgreSQL.
- **User-Friendly**: Simple and intuitive commands for easy interaction.
- **Dockerized**: Fully containerized for seamless deployment.
- **Extensible**: Easily add new features or metrics to track.

## Dependencies

- **python-telegram-bot**: Telegram Bot API
- **SQLAlchemy**: ORM for database interactions
- **Alembic**: Database migrations
- **PostgreSQL**: Database backend
- **Docker, Docker Compose**: For containerized deployment

## How It Works

1. **User** sends a command to log a health event (e.g., `/log_defecation` or `/log_asthma`).
2. **Bot** prompts the user for details, such as stool type or asthma symptoms (duration, reason, inhalation usage, and comments).
3. **Data** is stored in a PostgreSQL database.
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
   POSTGRES_USER=your_username
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=your_database
   POSTGRES_HOST=db
   POSTGRES_PORT=5432

   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   ```

3. Start all services:

   ```sh
   docker-compose up -d --build
   ```

### Usage

- Use the bot's main menu to select actions:
  - **Asthma Attack**: Log an asthma attack by providing details such as duration and reason.
  - **Defecation**: Log a defecation event by selecting the stool type.
  - **Export Data**: View or export health logs in various formats (CSV, markdown, or message).
- Follow the bot's prompts to complete each action.
- Use the "Back to Menu" button to return to the main menu at any time.

### Useful Commands

- Stop all services:

  ```sh
  docker-compose down
  ```

- Run migrations:

  ```sh
  docker-compose run --rm migrate
  ```

## Project Structure

```text
bot/
  db.py            # SQLAlchemy models and database logic
  main.py          # Telegram bot logic
  whitelist.txt    # User whitelist
alembic/
  env.py           # Alembic environment configuration
  versions/        # Alembic migration scripts
.env
.env.example
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
