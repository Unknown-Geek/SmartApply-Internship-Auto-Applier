/**
 * context-mode/server.js
 * Lightweight HTTP server providing SQLite FTS5 context indexing.
 * Exposes /index, /search, and /health endpoints.
 * Used by the SmartApply agent to avoid flooding the LLM with raw DOM text.
 */

const http = require("http");
const Database = require("better-sqlite3");
const path = require("path");
const fs = require("fs");

const PORT = process.env.PORT || 3100;
const DB_PATH = process.env.DB_PATH || "/app/data/context.db";

// Ensure data directory exists
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });

// ─── SQLite FTS5 Setup ────────────────────────────────────────────────────────
const db = new Database(DB_PATH);

db.exec(`
  CREATE VIRTUAL TABLE IF NOT EXISTS context_fts
  USING fts5(id, content, tokenize='trigram');
`);

const stmtInsert = db.prepare(`
  INSERT OR REPLACE INTO context_fts(id, content) VALUES (?, ?)
`);

const stmtSearch = db.prepare(`
  SELECT id, snippet(context_fts, 1, '<b>', '</b>', '...', 32) AS content
  FROM context_fts
  WHERE context_fts MATCH ?
  LIMIT ?
`);

const stmtDelete = db.prepare(`DELETE FROM context_fts WHERE id = ?`);

// ─── HTTP Server ──────────────────────────────────────────────────────────────

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => {
      try {
        resolve(JSON.parse(data || "{}"));
      } catch (e) {
        reject(new Error("Invalid JSON body"));
      }
    });
    req.on("error", reject);
  });
}

function send(res, status, body) {
  const json = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(json),
  });
  res.end(json);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);

  try {
    // ── GET /health ──────────────────────────────────────────────────────────
    if (req.method === "GET" && url.pathname === "/health") {
      return send(res, 200, { status: "ok", db: DB_PATH });
    }

    // ── POST /index ──────────────────────────────────────────────────────────
    if (req.method === "POST" && url.pathname === "/index") {
      const { id, content } = await readBody(req);
      if (!id || !content) {
        return send(res, 400, { error: "id and content are required" });
      }
      // Split large content into chunks of 2000 chars for better FTS recall
      const chunks = [];
      for (let i = 0; i < content.length; i += 2000) {
        chunks.push(content.slice(i, i + 2000));
      }
      db.transaction(() => {
        stmtDelete.run(id);
        chunks.forEach((chunk, idx) => {
          stmtInsert.run(`${id}:${idx}`, chunk);
        });
      })();
      return send(res, 200, {
        indexed: true,
        id,
        chunks: chunks.length,
        bytes: content.length,
      });
    }

    // ── POST /search ─────────────────────────────────────────────────────────
    if (req.method === "POST" && url.pathname === "/search") {
      const { query, limit = 5 } = await readBody(req);
      if (!query) {
        return send(res, 400, { error: "query is required" });
      }
      const results = stmtSearch.all(query, Math.min(limit, 20));
      return send(res, 200, { results, query });
    }

    // ── POST /clear ──────────────────────────────────────────────────────────
    if (req.method === "POST" && url.pathname === "/clear") {
      db.exec("DELETE FROM context_fts");
      return send(res, 200, { cleared: true });
    }

    return send(res, 404, { error: "Not found" });
  } catch (err) {
    console.error("[context-mode] Error:", err.message);
    return send(res, 500, { error: err.message });
  }
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`✅ [context-mode] SQLite FTS5 server running on port ${PORT}`);
  console.log(`   DB: ${DB_PATH}`);
});
