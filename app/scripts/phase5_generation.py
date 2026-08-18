import requests
from typing import Dict, Any, List
from phase4_retrieval_rerank import phase4_get_context_chunks, format_context, CFG


SYSTEM_PROMPT = """Anda ialah pembantu khidmat nasihat Bahasa Melayu yang rasmi, ringkas, dan patuh pada dokumen rujukan (gaya DBP).

Peraturan wajib:
1) Jawab HANYA berdasarkan KONTEXT yang diberi.
2) Jangan guna pengetahuan luar.
3) Jangan mereka-reka fakta, huraian, contoh, atau kesimpulan.
4) Jika tiada maklumat langsung dalam KONTEXT, jawab tepat:
"Maaf, maklumat tidak ditemui dalam dokumen rujukan yang ada."
5) Jika ada maklumat berkaitan tetapi tidak cukup untuk jawapan yang pasti, jawab tepat:
"Maklumat dalam dokumen rujukan tidak mencukupi untuk menentukan jawapan secara muktamad."
6) Jika KONTEXT mengandungi jawapan yang jelas, JANGAN tulis bahawa maklumat tidak ditemui.
7) Gunakan Bahasa Melayu formal dan jelas.
8) Jangan menyebut nombor dokumen seperti [1], [2], [3] dalam jawapan kepada pengguna.
9) Jangan sesekali menyebut atau menyalin doc_id, chroma_id, original_id, atomic_id, ID dokumen, metadata dalaman, atau nombor rujukan dalaman dalam jawapan kepada pengguna.
10) Jika soalan meminta maklumat semasa seperti "sekarang", "terkini", "siapa sekarang", "masa kini", atau fakta semasa di luar dokumen rujukan, dan KONTEXT tidak menyatakannya secara jelas, anda mesti jawab:
"Maaf, maklumat tidak ditemui dalam dokumen rujukan yang ada."
11) Jangan meneka nama orang, jawatan semasa, tarikh semasa, atau fakta semasa.
12) Jika anda menulis "Maaf, maklumat tidak ditemui dalam dokumen rujukan yang ada.", maka Huraian mesti ringkas dan tidak boleh mengandungi fakta tambahan daripada konteks.
13) Jika KONTEXT jelas menyokong jawapan, JANGAN tulis "maklumat tidak ditemui" atau "maklumat tidak mencukupi".
14) Jangan beri jawapan yang bercanggah antara "Jawapan Ringkas" dan "Huraian".
15) Jika soalan pengguna bertanya maksud umum sesuatu konsep, berikan definisi umum terlebih dahulu.
16) Jangan jawab berdasarkan contoh khusus sahaja kecuali soalan pengguna memang menyebut contoh tersebut.
17) Jika konteks mengandungi beberapa rekod, utamakan konteks yang paling umum dan paling hampir dengan soalan pengguna.
18) Jangan gabungkan maklumat yang bercanggah.
19) Jangan menyebut frasa seperti “Dokumen [1]”, “Dokumen [2]”, “Menurut dokumen”, atau apa-apa rujukan metadata dalaman dalam jawapan kepada pengguna.
20) Jika konteks mengandungi kesalahan ejaan kecil atau teks tidak kemas, betulkan ejaan secara minimum tanpa mengubah maksud asal.
21) Jangan menyebut nama buku, halaman, atau sumber tertentu kecuali maklumat tersebut jelas wujud dalam konteks yang diberikan.
22) Untuk soalan berbentuk “apakah maksud…”, berikan definisi umum terlebih dahulu, kemudian huraian ringkas dan contoh jika sesuai.
23) Jangan membuat kesimpulan bahawa sesuatu kedudukan adalah “paling biasa” kecuali dinyatakan dengan jelas dalam konteks.
24) Gunakan ayat yang ringkas, jelas, dan sesuai untuk pengguna umum.
25) Jika soalan meminta maksud umum sesuatu istilah, jawab dalam bentuk definisi umum. Jangan terlalu bergantung pada contoh khusus dalam konteks kecuali soalan pengguna menyebut contoh tersebut.
26) Jika konteks hanya mengandungi contoh khusus, nyatakan jawapan secara umum berdasarkan istilah utama tanpa membuat kesimpulan tambahan yang tidak jelas.
27) Jangan gunakan frasa “biasanya” atau “paling biasa” kecuali dinyatakan dengan jelas dalam konteks.
28) Betulkan kesalahan ejaan kecil daripada konteks seperti “nahunya” kepada “maknanya” jika pembetulan itu jelas dan tidak mengubah maksud.

Panduan mentafsir soalan:
A) Jika soalan meminta bentuk yang betul / ejaan yang betul / istilah yang betul:
- utamakan bentuk penggunaan standard yang tertera dalam KONTEXT
- JANGAN keliru antara bentuk kata dengan definisi kata

B) Jika soalan meminta maksud / definisi:
- jawab maksud berdasarkan KONTEXT sahaja

C) Jika soalan meminta contoh:
- beri contoh hanya jika contoh itu memang ada dalam KONTEXT
- jika tiada contoh dalam KONTEXT, tulis:
"Tiada contoh dalam konteks."

D) Jika soalan pengguna sangat umum tetapi KONTEXT hanya menyentuh sebahagian isu:
- jawab bahagian yang benar-benar disokong oleh KONTEXT sahaja

E) Jika soalan meminta pilihan bentuk kata seperti:
- "yang mana betul"
- "mana yang betul"
- "ejaan yang betul"
- "bentuk yang betul"

maka:
- jawab hanya bentuk yang benar-benar muncul sebagai bentuk standard dalam KONTEXT
- jangan cipta kategori tatabahasa yang tidak disebut dalam KONTEXT
- jangan gunakan huraian maksud untuk menukar bentuk kata

F) Jika soalan berbentuk ya/tidak seperti:
- "bolehkah ..."
- "adakah ..."
- "betulkah ..."

maka:
- jawab "Ya" atau "Tidak" jika KONTEXT jelas menyokongnya
- jangan tukar kepada jawapan "maklumat tidak ditemui" jika KONTEXT jelas menunjukkan penerimaan atau penolakan

Format jawapan:
Jawapan: [definisi atau jawapan utama dalam 1–2 ayat]
Huraian: [penjelasan ringkas berdasarkan konteks]
Contoh: [jika terdapat contoh yang sesuai dalam konteks]

Pastikan jawapan dipisahkan dengan jelas:
Jawapan: ...
Huraian: ...
Contoh: ...  (hanya jika sesuai)

Format jawapan wajib:

Jawapan:
<jawapan yang ringkas tetapi mesra pengguna. Jika sesuai, jawab dalam ayat penuh seperti:
- "Ya, penggunaan ini betul."
- "Bentuk yang betul ialah 'kerjasama'."
- "Maaf, saya tidak menemui maklumat tersebut dalam dokumen rujukan yang ada.">

Huraian:
<huraian ringkas, hanya berdasarkan KONTEXT>

Contoh:
<beri contoh daripada KONTEXT, atau tulis "Tiada contoh dalam konteks.">
"""


def call_lmstudio(prompt: str) -> str:
    url = CFG.lmstudio_base_url.rstrip("/") + "/chat/completions"

    payload = {
        "model": CFG.lmstudio_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    }

    r = requests.post(url, json=payload, timeout=CFG.lmstudio_timeout_s)
    if not r.ok:
        print("LM Studio error:", r.status_code, r.text)
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def looks_out_of_domain(q: str) -> bool:
    q = q.lower()
    blocked_patterns = [
        "perdana menteri",
        "presiden",
        "menteri sekarang",
        "harga",
        "cuaca",
        "bola sepak",
        "siapa sekarang",
        "terkini",
    ]
    return any(x in q for x in blocked_patterns)


def detect_question_type(q: str) -> str:
    ql = q.lower().strip()

    if any(x in ql for x in ["bolehkah", "adakah", "betulkah", "boleh ke"]):
        return "yes_no"

    if any(x in ql for x in ["maksud", "makna", "definisi", "erti"]):
        return "definition"

    if any(x in ql for x in ["contoh", "beri contoh", "bina ayat"]):
        return "example"

    if any(x in ql for x in ["perbezaan", "beza", "bezakan"]):
        return "comparison"

    if (" atau " in ql) or any(
        x in ql for x in ["mana yang betul", "yang mana betul", "ejaan yang betul", "bentuk yang betul"]
    ):
        return "choice"

    return "general"


def has_direct_evidence(question_type: str, query: str, final_chunks: list) -> bool:
    joined = " ".join(ch.get("document", "").lower() for ch in final_chunks)
    ql = query.lower().strip()

    if question_type == "yes_no":
        return True

    if question_type == "definition":
        return any(x in joined for x in ["bermaksud", "ialah", "makna", "maksud"])

    if question_type == "example":
        return any(x in joined for x in ["contoh", "misalnya", "sebagai contoh"])

    if question_type == "comparison":
        return any(x in joined for x in ["perbezaan", "berbeza", "manakala", "tetapi"])

    if question_type == "choice":
        has_choice_pattern = (
            (" atau " in ql)
            or any(
                x in ql
                for x in ["mana yang betul", "yang mana betul", "ejaan yang betul", "bentuk yang betul"]
            )
        )

        if not has_choice_pattern:
            return False

        # for choice questions, require definitional / contrast signals in context
        return any(x in joined for x in ["bermaksud", "ialah", "manakala", "kata nama", "kata adjektif"])

    return True


def build_type_instruction(question_type: str) -> str:
    if question_type == "yes_no":
        return (
            "Soalan ini ialah soalan ya/tidak. "
            "Jika konteks jelas menyokong, jawab 'Ya' atau 'Tidak' secara terus. "
            "Jangan tukar kepada jawapan umum."
        )

    if question_type == "definition":
        return (
            "Soalan ini meminta maksud atau definisi. "
            "Jawab dengan takrif yang paling langsung daripada konteks."
        )

    if question_type == "example":
        return (
            "Soalan ini meminta contoh. "
            "Beri contoh hanya jika contoh itu benar-benar ada dalam konteks. "
            "Jika tiada, tulis 'Tiada contoh dalam konteks.'"
        )

    if question_type == "comparison":
        return (
            "Soalan ini meminta perbezaan. "
            "Jawab hanya jika konteks benar-benar membandingkan unsur yang ditanya secara langsung. "
            "Jika konteks tidak menyatakan perbezaan secara jelas, jawab: "
            "\"Maklumat dalam dokumen rujukan tidak mencukupi untuk menentukan jawapan secara muktamad.\" "
            "Jangan tukar jawapan kepada contoh frasa lain yang tidak ditanya."
        )

    if question_type == "choice":
        return (
            "Soalan ini meminta pilihan bentuk yang betul. "
            "Pilih hanya satu bentuk yang paling jelas disokong sebagai bentuk standard dalam konteks. "
            "Jika satu bentuk muncul sebagai entri atau bentuk utama, dan satu lagi hanya muncul sebagai sebahagian huraian maksud, pilih bentuk utama itu. "
            "Jangan keliru antara bentuk kata dengan huraian maksud."
        )

    return "Jawab secara ringkas dan hanya berdasarkan konteks."


def generate_answer(user_query: str) -> Dict[str, Any]:
    if looks_out_of_domain(user_query):
        return {
            "answer": "Maaf, maklumat tidak ditemui dalam dokumen rujukan yang ada.",
            "contexts": [],
            "context_doc_ids": [],
            "debug": {
                "rule_based_refusal": "out_of_domain",
                "top_score": float("-inf"),
                "used_hyde": False,
                "expanded": False,
                "question_type": "out_of_domain",
            },
        }

    final_chunks, debug = phase4_get_context_chunks(user_query)

    if debug.get("prevalidation_failed") and debug.get("prevalidation_answer"):
        return {
            "answer": debug["prevalidation_answer"],
            "contexts": [],
            "context_doc_ids": [],
            "debug": debug,
        }

    top_score = debug.get("top_score", float("-inf"))

    if (not final_chunks) or (top_score < 1.5):
        return {
            "answer": "Maaf, maklumat tidak ditemui dalam dokumen rujukan yang ada.",
            "contexts": [],
            "context_doc_ids": [],
            "debug": debug,
        }

    question_type = detect_question_type(user_query)

    if not has_direct_evidence(question_type, user_query, final_chunks):
        return {
            "answer": "Maklumat dalam dokumen rujukan tidak mencukupi untuk menentukan jawapan secara muktamad.",
            "contexts": [ch.get("document", "") for ch in final_chunks],
            "context_doc_ids": [
                (ch.get("metadata") or {}).get("doc_id", ch.get("id", ""))
                for ch in final_chunks
            ],
            "debug": {**debug, "question_type": question_type, "evidence_check": "failed"},
        }

    if question_type == "comparison":
        joined_context = " ".join(
            ch.get("document", "").lower() for ch in final_chunks
        )

        direct_compare_signals = [
            "perbezaan",
            "berbeza",
            "manakala",
            "tetapi",
        ]

        has_direct_compare = any(sig in joined_context for sig in direct_compare_signals)

        ql = user_query.lower()
        important_terms = []
        for term in ["amat", "sangat", "sekali", "sungguh"]:
            if term in ql:
                important_terms.append(term)

        has_terms = all(term in joined_context for term in important_terms) if important_terms else True

        if (not has_direct_compare) or (not has_terms):
            return {
                "answer": "Maklumat dalam dokumen rujukan tidak mencukupi untuk menentukan jawapan secara muktamad.",
                "contexts": [ch.get("document", "") for ch in final_chunks],
                "context_doc_ids": [
                    (ch.get("metadata") or {}).get("doc_id", ch.get("id", ""))
                    for ch in final_chunks
                ],
                "debug": {**debug, "question_type": question_type, "comparison_guard": "failed"},
            }

    context_string = format_context(final_chunks)
    type_instruction = build_type_instruction(question_type)

    user_prompt = f"""
KONTEXT:
{context_string}

ARAHAN TAMBAHAN:
{type_instruction}

SOALAN:
{user_query}
"""

    answer = call_lmstudio(user_prompt)

    contexts = [ch.get("document", "") for ch in final_chunks]
    context_doc_ids = [
        (ch.get("metadata") or {}).get("doc_id", ch.get("id", ""))
        for ch in final_chunks
    ]

    return {
        "answer": answer,
        "contexts": contexts,
        "context_doc_ids": context_doc_ids,
        "debug": {**debug, "question_type": question_type},
    }


def answer_question(question: str) -> Dict[str, Any]:
    result = generate_answer(question)
    debug = result.get("debug", {}) or {}

    return {
        "answer": result.get("answer", ""),
        "top_score": debug.get("top_score"),
        "used_hyde": debug.get("used_hyde"),
        "expanded": debug.get("expanded"),
        "retrieved_contexts": result.get("contexts", []),
    }