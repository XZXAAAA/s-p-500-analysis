# Frontend - React Application

## Overview

Modern React + TypeScript frontend for S&P 500 Stock Sentiment Analysis.

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI** - Component library
- **Vite** - Build tool
- **Axios** - HTTP client
- **React Router** - Routing
- **Plotly.js** - Data visualization
- **Vitest** - Testing framework

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development Server

```bash
npm run dev
```

Access at: http://localhost:3000

### Build for Production

```bash
npm run build
```

### Preview Production Build

```bash
npm run preview
```

## Testing

### Run Tests

```bash
npm test
```

### Run Tests with UI

```bash
npm run test:ui
```

### Generate Coverage Report

```bash
npm run test:coverage
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client
│   ├── pages/            # Page components
│   ├── __tests__/        # Test files
│   ├── App.tsx           # Main app component
│   └── main.tsx          # Entry point
├── public/               # Static assets
├── Dockerfile            # Docker configuration
└── package.json          # Dependencies
```

## Available Pages

- `/login` - User login
- `/register` - User registration
- `/dashboard` - Main dashboard with sentiment data
- `/analytics` - Advanced analytics (coming soon)

## Environment Variables

Create `.env` file:

```env
VITE_API_URL=http://localhost:5000
```

## Docker

### Build Image

```bash
docker build -t sentiment-frontend .
```

### Run Container

```bash
docker run -p 3000:80 sentiment-frontend
```

## Contributing

1. Create feature branch
2. Write tests
3. Implement feature
4. Ensure tests pass
5. Submit pull request

## License

MIT

