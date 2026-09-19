export default function handler(request, response) {
  if (request.method !== "POST") return response.status(405).json({ detail: "Kaedah tidak dibenarkan." });
  const rating = request.body?.rating;
  if (!["helpful", "unhelpful"].includes(rating)) {
    return response.status(422).json({ detail: "Penilaian tidak sah." });
  }
  const correction = String(request.body?.correction || "").trim();
  if (rating === "unhelpful" && (correction.length < 3 || correction.length > 2000)) {
    return response.status(422).json({ detail: "Sila berikan pembetulan antara 3 hingga 2000 aksara." });
  }
  return response.status(201).json({ status: "accepted", learning_mode: "browser-feedback-memory" });
}
