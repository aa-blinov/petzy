# Cat Health Control

## Overview

**Cat Health Control** is a web application designed to help cat owners track their pet's health. The application allows users to log and monitor key health metrics, such as defecation events, stool types, asthma symptoms, weight measurements, and other relevant data, ensuring better care for their feline companions.

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
- **Docker, Docker Compose**: For containerized deployment

## Getting Started

### Prerequisites

- Docker and Docker Compose

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
   FLASK_SECRET_KEY=your-secret-key-for-sessions
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD_HASH=your_bcrypt_password_hash
   ```

   To generate a password hash, run:
   ```bash
   python -c "import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())"
   ```
   
   Or use the default password "admin123" (not recommended for production).

3. Start all services:

   ```sh
   docker-compose up -d --build
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

### Useful Commands

- Stop all services:

  ```sh
  docker-compose down
  ```

- View logs:

  ```sh
  docker-compose logs -f web
  ```

## Project Structure

```text
web/
  app.py           # Flask web application
  main.py          # Web app entry point
  db.py            # MongoDB database connection
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
```

## Contributing

Pull requests and suggestions are welcome! Please open an issue or submit a PR to help improve the project.

## License

This project is licensed under the MIT License. See the [LICENSE](https://opensource.org/license/mit) file for details.
