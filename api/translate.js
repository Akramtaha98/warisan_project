import { createTranslationResponse } from "./_lib/chat-core.js";

const windows = new Map();
const WINDOW_MS = 60_000;
const MAX_REQUESTS = 12;

function allowed(ip) {
  const now = Date.now();
  const active = (windows.get(ip) || []).filter((timestamp) => now - timestamp < WINDOW_MS);
  if (active.length >= MAX_REQUESTS) return false;
  active.push(now);
  windows.set(ip, active);
  return true;
}

export default async function handler(request, response) {
  if (request.method !== "POST") return response.status(405).json({ detail: "Kaedah tidak dibenarkan." });
  const ip = String(request.headers["x-forwarded-for"] || request.socket?.remoteAddress || "unknown").split(",")[0].trim();
  if (!allowed(ip)) return response.status(429).json({ detail: "Terlalu banyak permintaan terjemahan. Cuba lagi sebentar." });
  try {
    const result = await createTranslationResponse(request.body, { token: request.headers["x-vercel-oidc-token"] });
    return response.status(200).json(result);
  } catch (error) {
    console.error("Translation request failed:", error?.message || error);
    const status = Number(error.statusCode) || 503;
    const detail = status < 500 ? error.message : "Terjemahan belum tersedia. Sila cuba lagi sebentar.";
    return response.status(status).json({ detail });
  }
}
