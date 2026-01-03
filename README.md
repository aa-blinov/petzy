# Petzy

## Overview

**Petzy** is a Progressive Web App (PWA) designed to help pet owners track their pet's health. The application allows users to log and monitor key health metrics, such as defecation events, stool types, asthma symptoms, weight measurements, eye drops, tooth brushing, and ear cleaning, ensuring better care for their pets.

## Features

### Core Functionality
- **Health Tracking**: Log various health events:
  - Asthma attacks (duration, inhalation, reason)
  - Defecation (stool type, color, food)
  - Weight measurements (with food tracking)
  - Eye drops administration
  - Tooth brushing
  - Ear cleaning
- **Pet Management**: Create, edit, and manage multiple pets with photos
- **Pet Sharing**: Share access to pets with other users
- **History View**: View and edit all health records with filtering by type
- **Data Export**: Export health logs in various formats (CSV, TSV, HTML, Markdown)

### User Experience
- **Progressive Web App (PWA)**: Installable on mobile devices with offline support
- **Mobile-First Design**: Optimized for mobile devices with native-feeling UI
- **Dark Theme**: Toggle between light and dark themes
- **Customizable Dashboard**: Reorder and hide dashboard tiles
- **Form Defaults**: Set default values for each health record type
- **Responsive Design**: Works seamlessly on desktop and mobile

### Technical
- **Modern Frontend**: React + TypeScript + Vite with code splitting
- **Backend API**: Flask REST API with MongoDB
- **Caching**: React Query for efficient data caching
- **Service Worker**: Offline support and asset caching
- **Dockerized**: Fully containerized with Docker Compose
- **Nginx Reverse Proxy**: Production-ready setup with compression

## Tech Stack

### Backend
- **Python 3.12**: Backend runtime
- **Flask**: Web framework
- **pymongo**: MongoDB client
- **gunicorn**: Production WSGI server
- **flask-cors**: CORS support

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool and dev server
- **antd-mobile**: Mobile UI component library
- **React Query**: Data fetching and caching
- **React Router**: Client-side routing
- **React Hook Form**: Form management
- **Zod**: Schema validation

### Infrastructure
- **Docker & Docker Compose**: Containerization
- **Nginx**: Reverse proxy and static file serving
- **MongoDB**: Database
- **Service Worker**: PWA and offline support

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
   - `ADMIN_USERNAME` - Admin username (default: `admin`)
   - `BACKUP_RETENTION_DAYS` - Days to keep backups (default: 7)
   - `GUNICORN_WORKERS` - Number of Gunicorn workers (default: 2)

   To generate a password hash, run:
   ```bash
   python -c "import bcrypt; print(bcrypt.hashpw('your_password'.encode(), bcrypt.gensalt()).decode())"
   ```

3. Start all services:

   ```sh
   docker-compose up -d --build
   ```

   The application will be available at `http://localhost:3000` (or the port configured in your environment).

   **Services**:
   - **Nginx** (port 3000): Reverse proxy serving frontend and proxying API requests
   - **Flask Backend** (port 5000): REST API with Gunicorn (2 workers by default)
   - **MongoDB** (port 27017): Database
   - **Mongo Backup**: Automated backup service

   You can override the number of Gunicorn workers by setting `GUNICORN_WORKERS` environment variable.
   
### Development

#### Frontend Development

```sh
cd frontend
npm install
npm run dev  # Starts Vite dev server on http://localhost:5173
```

The frontend dev server proxies API requests to `http://localhost:5001` (configured in `vite.config.ts`).

#### Backend Development

For local development without Docker:

```sh
# Development mode (with debug)
export FLASK_DEBUG=true
python -m web.app

# Or use Gunicorn directly (2 workers by default)
gunicorn -c gunicorn.conf.py web.app:app

# Or specify custom number of workers
gunicorn -c gunicorn.conf.py --workers 4 web.app:app
```

**Note**: Make sure MongoDB is running and accessible.

### Usage

#### Web Interface

1. Access the web interface at `http://localhost:3000` (or the port configured in your environment)
2. Login with credentials (set in `.env` file):
   - Username: `admin` (or value from `ADMIN_USERNAME`)
   - Password: Set via `ADMIN_PASSWORD_HASH` environment variable
3. **Dashboard**: Quick access to create new health records
4. **History**: View and edit all past health records, filter by type, export data
5. **Pets Management**: Create, edit, and manage your pets; share access with other users
6. **Settings**:
   - **Theme**: Toggle between light and dark themes
   - **Form Defaults**: Set default values for each health record type
   - **Tiles Settings**: Customize dashboard tile order and visibility
7. **Admin Panel**: User management (admin only)

#### Mobile Installation (PWA)

1. Open the app in a mobile browser (Chrome/Safari)
2. Use "Add to Home Screen" option
3. The app will install as a native-like application
4. Works offline with cached data

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

- **Stop all services**:
  ```sh
  docker-compose down
  ```

- **View logs**:
  ```sh
  docker-compose logs -f web          # Backend logs
  docker-compose logs -f frontend     # Frontend build logs
  docker-compose logs -f nginx        # Nginx logs
  docker-compose logs -f mongo-backup # Backup service logs
  ```

- **Rebuild specific service**:
  ```sh
  docker-compose up -d --build frontend  # Rebuild frontend only
  docker-compose up -d --build web       # Rebuild backend only
  ```

- **Access services**:
  - Frontend: `http://localhost:3000`
  - Backend API: `http://localhost:3000/api/`
  - MongoDB: `localhost:27017` (if exposed)

- **Run tests**:
  ```sh
  # Backend tests
  cd /path/to/project
  pytest

  # With coverage
  pytest --cov=web --cov-report=html
  ```

## Project Structure

```text
├── frontend/              # React frontend application
│   ├── src/
│   │   ├── components/    # React components
│   │   │   ├── Navbar.tsx
│   │   │   ├── BottomTabBar.tsx
│   │   │   └── ...
│   │   ├── pages/         # Page components
│   │   │   ├── Dashboard.tsx
│   │   │   ├── History.tsx
│   │   │   ├── Pets.tsx
│   │   │   ├── Settings.tsx
│   │   │   └── ...
│   │   ├── services/      # API services
│   │   ├── hooks/         # Custom React hooks
│   │   ├── utils/         # Utility functions
│   │   └── styles/        # Global styles
│   ├── public/            # Static assets
│   ├── package.json       # Frontend dependencies
│   └── vite.config.ts     # Vite configuration
├── web/                   # Flask backend API
│   ├── app.py            # Main Flask application
│   ├── auth.py          # Authentication logic
│   ├── pets.py          # Pet management endpoints
│   ├── health_records.py # Health record endpoints
│   ├── users.py         # User management
│   ├── export.py        # Data export functionality
│   └── db.py            # MongoDB connection
├── nginx/                # Nginx configuration
│   └── nginx.conf       # Reverse proxy config
├── scripts/              # Utility scripts
│   ├── mongo-backup.sh  # Automated backup script
│   └── mongo-backup-manual.sh
├── tests/                # Backend tests
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile           # Backend Docker image
├── frontend/Dockerfile  # Frontend Docker image
├── nginx/Dockerfile     # Nginx Docker image
├── gunicorn.conf.py     # Gunicorn configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Contributing

Pull requests and suggestions are welcome! Please open an issue or submit a PR to help improve the project.

## License

This project is licensed under the MIT License. See the [LICENSE](https://opensource.org/license/mit) file for details.
