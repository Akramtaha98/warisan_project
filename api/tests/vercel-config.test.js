import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("Vercel builds the Vite frontend and bounds the chat function", async () => {
  const config = JSON.parse(await readFile(new URL("../../vercel.json", import.meta.url)));
  assert.equal(config.framework, "vite");
  assert.equal(config.outputDirectory, "frontend/dist");
  assert.equal(config.functions["api/chat.js"].maxDuration, 60);
});

test("deployment excludes local databases, secrets, models, and development caches", async () => {
  const ignored = (await readFile(new URL("../../.vercelignore", import.meta.url), "utf8")).split(/\r?\n/);
  for (const required of [
    ".env",
    ".env.*",
    "/data",
    "frontend/node_modules",
    "requirements.txt",
    "*.sqlite3",
  ]) {
    assert.ok(ignored.includes(required), `missing ${required}`);
  }
});
