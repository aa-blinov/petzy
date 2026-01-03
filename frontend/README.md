# Petzy Frontend

React + TypeScript frontend for Petzy pet health tracking application.

## Tech Stack

- **React 19** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **React Router** - Routing
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Axios** - HTTP client
- **Vite PWA Plugin** - PWA support
- **React Hook Form** - Form handling
- **Zod** - Schema validation
- **@dnd-kit** - Drag and drop

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Environment Variables

Create a `.env` file:

```
VITE_API_URL=http://localhost:5001/api
```

## Docker

```bash
# Build Docker image
docker build -t petzy-frontend .

# Run container
docker run -p 3000:80 petzy-frontend
```

## Project Structure

```
frontend/
├── public/          # Static assets
├── src/
│   ├── components/  # Reusable components
│   ├── pages/       # Page components
│   ├── services/     # API services
│   ├── hooks/       # Custom React hooks
│   ├── utils/       # Utility functions
│   └── styles/      # Global styles
└── nginx.conf       # Nginx configuration for production
```

## Features

- ✅ Authentication with JWT
- ✅ Dashboard with customizable tiles
- ✅ Health record forms
- ✅ History with pagination
- ✅ Settings management
- ✅ PWA support
- ✅ Responsive design

## Notes

- The old implementation in `web/` remains untouched
- Both versions can run in parallel
- API endpoints are proxied through Nginx in production
