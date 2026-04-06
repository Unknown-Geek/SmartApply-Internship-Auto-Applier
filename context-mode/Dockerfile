# context-mode/Dockerfile
# Lightweight Node.js container providing SQLite FTS5 context indexing via HTTP API

FROM node:20-slim

WORKDIR /app

# Install better-sqlite3 (needs build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package.json .
RUN npm install --production

COPY server.js .

RUN mkdir -p /app/data

EXPOSE 3100

CMD ["node", "server.js"]
