import { DEFAULT_FREE_MODEL, DEFAULT_MODEL } from "./_lib/chat-core.js";
import { records } from "./_lib/retrieval.js";

export default function handler(request, response) {
  const authenticated = Boolean(
    process.env.OPENROUTER_API_KEY ||
    process.env.AI_GATEWAY_API_KEY ||
    process.env.VERCEL_OIDC_TOKEN ||
    request.headers["x-vercel-oidc-token"],
  );
  return response.status(200).json({
    status: authenticated ? "ready" : "degraded",
    database_ready: true,
    model_ready: authenticated,
    model: process.env.QWEN_MODEL || (process.env.OPENROUTER_API_KEY ? DEFAULT_FREE_MODEL : DEFAULT_MODEL),
    provider: process.env.OPENROUTER_API_KEY ? "openrouter-free" : "vercel-ai-gateway",
    collection: "Malay QA synthetic demo",
    records: records.length,
    mode: "vercel-demo",
  });
}
