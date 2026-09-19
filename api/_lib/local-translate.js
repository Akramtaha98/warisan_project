const PHRASES = [
  [/Tanda soal diletakkan pada akhir ayat tanya langsung\.?/gi, "A question mark is placed at the end of a direct question."],
  [/Fungsi tanda soal ialah diletakkan pada akhir ayat tanya langsung\.?/gi, "The function of a question mark is to mark the end of a direct question."],
  [/Bilakah mesyuarat itu akan bermula\?/gi, "When will the meeting begin?"],
  [/Salam\. Ada apa yang boleh saya bantu dalam bidang Bahasa Melayu\?/gi, "Hello. How can I help you with the Malay language?"],
  [/Hai! Saya \*\*Warisan\*\*, pembantu Bahasa Melayu\./gi, "Hi! I am **Warisan**, a Malay-language assistant."],
  [/Anda boleh bertanya tentang ejaan, tatabahasa, istilah, tanda baca atau penggunaan kata\./gi, "You can ask about spelling, grammar, terminology, punctuation, or word usage."],
  [/Berdasarkan rekod dataset yang paling berkaitan:/gi, "Based on the most relevant dataset record:"],
  [/Saya menyemak (\d+) rekod dataset yang paling berkaitan\. Berdasarkan padanan terkuat:/gi, "I checked the $1 most relevant dataset records. Based on the strongest match:"],
  [/Contohnya,/gi, "For example,"],
  [/Contohnya ialah/gi, "Examples include"],
  [/Ayat yang betul ialah/gi, "The correct sentence is"],
  [/Bentuk yang betul ialah/gi, "The correct form is"],
  [/Perkataan yang betul ialah/gi, "The correct word is"],
  [/ditulis secara terpisah/gi, "is written separately"],
  [/ditulis secara rapat/gi, "is written as one word"],
  [/digunakan untuk/gi, "is used to"],
  [/digunakan sebelum/gi, "is used before"],
  [/digunakan pada/gi, "is used at"],
  [/pada akhir ayat/gi, "at the end of a sentence"],
  [/ayat tanya langsung/gi, "a direct question"],
  [/Bahasa Melayu/gi, "the Malay language"],
];

const WORDS = new Map(Object.entries({
  adalah: "is", ialah: "is", dan: "and", atau: "or", dengan: "with", tanpa: "without",
  dalam: "in", daripada: "from", dari: "from", kepada: "to", untuk: "for", pada: "at",
  sebelum: "before", selepas: "after", antara: "between", sebagai: "as", kerana: "because",
  tetapi: "but", manakala: "whereas", namun: "however", juga: "also", hanya: "only",
  kata: "word", ayat: "sentence", frasa: "phrase", nama: "noun", kerja: "verb",
  adjektif: "adjective", sendi: "preposition", imbuhan: "affix", awalan: "prefix",
  akhiran: "suffix", ejaan: "spelling", istilah: "term", maksud: "meaning",
  fungsi: "function", tanda: "mark", soal: "question", koma: "comma", baca: "punctuation",
  betul: "correct", salah: "incorrect", tepat: "accurate", baku: "standard",
  digunakan: "used", penggunaan: "usage", ditulis: "written", diletakkan: "placed",
  menunjukkan: "indicates", menyatakan: "expresses", menerangkan: "explains",
  memisahkan: "separates", membentuk: "forms", mempunyai: "has", perlu: "should",
  boleh: "can", lazimnya: "usually", sering: "often", tidak: "not", lebih: "more",
  satu: "one", dua: "two", bentuk: "form", rasmi: "formal", umum: "general",
  tempat: "place", waktu: "time", arah: "direction", penerima: "recipient",
  perbuatan: "action", keadaan: "condition", bahagian: "part", penjelasan: "explanation",
  senarai: "list", langsung: "direct", akhir: "end", awal: "beginning",
  ini: "this", itu: "that", tersebut: "that", yang: "which", apabila: "when",
  jika: "if", supaya: "so that", serta: "and", contoh: "example",
}));

export function translateMalayLocally(value) {
  let translated = String(value || "").trim();
  for (const [pattern, replacement] of PHRASES) translated = translated.replace(pattern, replacement);
  translated = translated.replace(/\b[\p{L}-]+\b/gu, (word) => {
    const replacement = WORDS.get(word.toLocaleLowerCase("ms"));
    if (!replacement) return word;
    return /^[A-Z]/.test(word) ? replacement.charAt(0).toUpperCase() + replacement.slice(1) : replacement;
  });
  return translated
    .replace(/\s+([,.!?;:])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
}
