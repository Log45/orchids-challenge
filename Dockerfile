# Stage 1: Frontend Build
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Backend Build
FROM python:3.11-slim AS backend-builder
WORKDIR /app/backend

# # Install system dependencies first
# RUN apt-get update && apt-get install -y \
#     libglib2.0-0 \
#     libnss3 \
#     libnspr4 \
#     libatk1.0-0 \
#     libatk-bridge2.0-0 \
#     libcups2 \
#     libdrm2 \
#     libdbus-1-3 \
#     libxkbcommon0 \
#     libxcomposite1 \
#     libxdamage1 \
#     libxfixes3 \
#     libxrandr2 \
#     libgbm1 \
#     libasound2 \
#     libpango-1.0-0 \
#     libpangocairo-1.0-0 \
#     && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps
COPY backend/ .

# Final stage (only fix shown here)
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies for Playwright and Node.js
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Install Playwright for browser automation
RUN npx -y playwright@1.52.0 install chromium --with-deps

# Copy frontend build
COPY --from=frontend-builder /app/frontend/ ./frontend/

# Copy backend code
COPY backend/ ./backend

# Copy start script
COPY start.sh /app/start.sh
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 8000 3000

# Environment variables
ENV PYTHONPATH=/app
ENV PATH="/usr/local/bin:${PATH}"
# ENV PORT=8000
ENV NEXT_PUBLIC_API_URL=http://localhost:3000

CMD ["/app/start.sh"]