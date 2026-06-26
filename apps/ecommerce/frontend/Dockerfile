FROM node:22-alpine

WORKDIR /app

# Copy dependency files first for layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application code
COPY frontend/ .

EXPOSE 3001

# NOTE: This runs the Vite dev server, which is not suitable for production.
# For production, run "npm run build" and serve the dist/ folder with a static server (e.g. nginx).
CMD ["npx", "vite", "--host", "0.0.0.0", "--port", "3001"]
