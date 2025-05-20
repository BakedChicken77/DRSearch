# DRSearch Project Guide for Codex

## Project Overview

DRSearch is a search application consisting of two main components:

- `drsearch_frontend`: A Next.js-based React frontend application with TypeScript
- `drsearch_backend`: A FastAPI-based Python backend application using LangChain

The project leverages vector search (Weaviate) and PostgreSQL for data storage.

## Architecture

The application consists of:
- **Frontend**: Next.js 13.5 React application with Chakra UI and TypeScript
- **Backend**: FastAPI Python API with LangChain integration
- **Database**: PostgreSQL for structured data storage
- **Vector Database**: Weaviate for vector search capabilities
- **Deployment**: Docker-based deployment using docker-compose

## Environment Setup

### Backend Setup

```bash
# Install Python dependencies using Poetry
cd drsearch_backend
poetry install

# Set up environment variables
cp .example.env .env
# Edit .env file with your specific configuration
```

### Frontend Setup

```bash
# Install Node.js dependencies
cd drsearch_frontend
yarn install
```

### Docker Deployment

```bash
# Run the full application stack
docker-compose -f docker-compose.fullapp.yml up -d
```

## Testing Instructions

### Backend Testing
- Run all unit tests with coverage reporting:
  ```bash
  cd drsearch_backend
  poetry run pytest --cov=app --cov-report=term-missing -q
  ```
- For specific test files:
  ```bash
  poetry run pytest tests/path/to/test_file.py -v
  ```

### Frontend Testing
- Run the linter:
  ```bash
  cd drsearch_frontend
  yarn lint
  ```
- Format the code:
  ```bash
  yarn format
  ```
- Run all unit tests with coverage reporting:
  ```bash
  cd drsearch_frontend
  yarn test --coverage
  ```

## Development Workflow

### Backend Development
1. Make changes to Python files in the `drsearch_backend/app` directory
2. Test changes with the appropriate unit tests in `drsearch_backend/tests`
3. Follow PEP 8 style guidelines and use Black for formatting
4. Ensure type annotations are used throughout the codebase

### Frontend Development
1. Make changes to TypeScript/TSX files in the `drsearch_frontend/app` directory
2. Follow the component structure established in the codebase
3. Use Prettier for code formatting
4. Ensure proper TypeScript types are defined

## Code Structure

### Backend Structure
- `app/main.py`: FastAPI application entry point
- `app/api/`: API endpoints
- `app/core/`: Core application logic and configuration
- `app/chain/`: LangChain components and chains
- `app/auth/`: Authentication logic
- `tests/`: Unit tests

### Frontend Structure
- `app/page.tsx`: Main page component
- `app/components/`: Reusable React components
- `app/api/`: API routes
- `app/utils/`: Utility functions
- `lib/`: Shared libraries and utilities for the frontend

## Pull Request Guidelines

- Include detailed description of changes
- Reference any related issues
- Ensure all tests pass
- Follow the established code style

## Debugging Instructions

### Backend Debugging
- Check logs for error messages
- Use Python's built-in debugging tools
- Review the FastAPI documentation at `/docs` endpoint when the server is running

### Frontend Debugging
- Use browser developer tools for frontend issues
- Check the browser console for JavaScript errors
- Use React DevTools for component debugging

## Common Tasks

### Adding a New API Endpoint
1. Create a new route file in `drsearch_backend/app/api/`
2. Define the endpoint using FastAPI decorators
3. Add appropriate request/response models
4. Add unit tests in `tests/api/`

### Adding a New Frontend Component
1. Create a new component file in `drsearch_frontend/app/components/`
2. Export the component and import it where needed
3. Use TypeScript interfaces for props
4. Follow the established styling patterns with Chakra UI

## Important Notes

- The project uses environment variables extensively. Always check `.env` files for configuration.
- The backend relies on LangChain for AI functionality.
- The frontend uses Next.js 13's App Router pattern.
- Authentication is handled via JWT.

