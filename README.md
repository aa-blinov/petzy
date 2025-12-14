# Petzy

## Overview

**Petzy** is a web application designed to help pet owners track their pet's health. The application allows users to log and monitor key health metrics, such as defecation events, stool types, asthma symptoms, weight measurements, and other relevant data, ensuring better care for their pets.

## Features

- **Health Tracking**: Log defecation events with stool type classification, asthma symptoms (including duration, reason, and inhalation usage), and weight measurements
- **Food Tracking**: Record food information for each entry
- **Data Storage**: Persistent storage using MongoDB
- **Data Export**: Export health logs in various formats (CSV, TSV, HTML, Markdown)
- **User-Friendly**: Modern web interface with authentication and mobile-responsive design
- **Dockerized**: Fully containerized for seamless deployment
- **Extensible**: Easily add new features or metrics to track

## Dependencies

- **pymongo**: MongoDB client for Python
- **flask**: Web framework
- **werkzeug**: WSGI utilities
- **gunicorn**: Production WSGI server (used in Docker)
- **Docker, Docker Compose**: For containerized deployment

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Installation & Run

1. Clone the repository:

   ```sh
   git clone <repo-url>
   cd petzy
   ```

2. Create a `.env` file based on `.env.example`:

   ```sh
   cp .env.example .env
   ```

   Then edit `.env` and set your values. Required variables:
   - `MONGO_USER`, `MONGO_PASS`, `MONGO_DB` - MongoDB credentials
   - `FLASK_SECRET_KEY` - Secret key for Flask sessions (change in production!)
   - `ADMIN_PASSWORD_HASH` - Bcrypt hash of admin password

   To generate a password hash, run:
   ```bash
   python -c "import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())"
   ```

3. Start all services:

   ```sh
   docker-compose up -d --build
   ```

   The application runs with **Gunicorn** (production WSGI server) in Docker containers with **2 workers** by default. You can override this by setting `GUNICORN_WORKERS` environment variable.
   
   For local development without Docker, you can run:
   
   ```sh
   # Development mode (with debug)
   export FLASK_DEBUG=true
   python -m web.main
   
   # Or use Gunicorn directly (2 workers by default)
   gunicorn -c gunicorn.conf.py web.app:app
   
   # Or specify custom number of workers
   gunicorn -c gunicorn.conf.py --workers 4 web.app:app
   ```

### Usage

#### Web Interface

1. Access the web interface at `http://localhost:5001`
2. Login with credentials (set in `.env` file):
   - Username: `admin` (or value from `ADMIN_USERNAME`)
   - Password: Set via `ADMIN_PASSWORD_HASH` environment variable
3. Use the dashboard to:
   - Record asthma attacks with full details
   - Record defecation events with food information
   - Record weight measurements with food information
   - View history of all recorded events
   - Export data in various formats (CSV, TSV, HTML, Markdown)
4. The interface is fully responsive and works on mobile devices

### MongoDB Backups

The application includes an automated backup service (`mongo-backup`) that:

- **Automatically creates backups** every 24 hours
- **Stores backups** in the `./backups/` directory (mounted as volume)
- **Retains backups** for 7 days (configurable via `BACKUP_RETENTION_DAYS` in `.env`)
- **Uses gzip compression** to save disk space
- **Runs continuously** as a Docker service

Backups are stored with timestamps: `backup-YYYYMMDD_HHMMSS/`

To manually trigger a one-time backup:

```sh
./scripts/mongo-backup-manual.sh
```

To view backup service logs:

```sh
docker-compose logs -f mongo-backup
```

**Note**: The `backups/` directory is excluded from git (see `.gitignore`). Make sure to regularly copy backups to a safe location for disaster recovery.

### Useful Commands

- Stop all services:

  ```sh
  docker-compose down
  ```

- View logs:

  ```sh
  docker-compose logs -f web
  docker-compose logs -f mongo-backup
  ```

## Project Structure

```text
web/
  app.py           # Flask web application
  main.py          # Web app entry point
  db.py            # MongoDB database connection
  configs.py       # Application configuration
  templates/       # HTML templates
    base.html
    login.html
    dashboard.html
  static/          # Static files (CSS, JS)
    css/
      style.css
scripts/
  mongo-backup.sh       # MongoDB backup script (runs in container)
  backup-mongo-test.sh  # Manual backup test script
backups/           # MongoDB backups directory (auto-created, git-ignored)
.env               # Environment variables (create from .env.example)
.env.example       # Example environment variables
docker-compose.yml # Docker Compose configuration
Dockerfile         # Docker image definition
gunicorn.conf.py   # Gunicorn server configuration (2 workers by default)
README.md          # This file
requirements.txt   # Python dependencies
```

## Contributing

Pull requests and suggestions are welcome! Please open an issue or submit a PR to help improve the project.

## License

This project is licensed under the MIT License. See the [LICENSE](https://opensource.org/license/mit) file for details.
