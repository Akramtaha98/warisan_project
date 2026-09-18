import { BookOpenText, Languages, Scale, SpellCheck2 } from "lucide-react";

export const suggestions = [
  {
    icon: Scale,
    label: "Bandingkan istilah",
    prompt: "Apakah perbezaan antara 'ialah' dengan 'adalah'?",
  },
  {
    icon: SpellCheck2,
    label: "Semak ejaan",
    prompt: "Yang manakah ejaan yang betul, 'kerjasama' atau 'kerja sama'?",
  },
  {
    icon: Languages,
    label: "Fahami penggunaan",
    prompt: "Bagaimanakah perkataan 'justeru' digunakan dengan betul?",
  },
  {
    icon: BookOpenText,
    label: "Tanya maksud",
    prompt: "Apakah maksud peribahasa 'bagai aur dengan tebing'?",
  },
];

export const intentLabels = {
  comparison: "Perbandingan",
  correction: "Pembetulan ayat",
  grammar: "Tatabahasa",
  multi_part: "Soalan berangkai",
  choice: "Pilihan bentuk",
  definition: "Maksud & definisi",
  example: "Contoh ayat",
  yes_no: "Semakan",
  spelling_or_term: "Ejaan & istilah",
  usage: "Penggunaan",
  general: "Khidmat bahasa",
};
