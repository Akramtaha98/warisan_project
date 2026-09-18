export default function handler(request, response) {
  if (request.method !== "POST") return response.status(405).json({ detail: "Kaedah tidak dibenarkan." });
  const rating = request.body?.rating;
  if (!["helpful", "unhelpful"].includes(rating)) {
    return response.status(422).json({ detail: "Penilaian tidak sah." });
  }
  return response.status(201).json({ status: "accepted" });
}
