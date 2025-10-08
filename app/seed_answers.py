# seed_answers.py
import sqlite3, os

DB_PATH = os.getenv("DB_PATH", "gita.db")

# Define canonical answers here
ANSWERS = {
    # --- Sthita-prajna ---
    "What is sthita prajna?": {
        "short": (
            "One who is sthita-prajña is steady in wisdom and free from agitation. "
            "Verses [2:55–2:72] describe such a sage: content in the Self, without craving, "
            "unshaken by sorrow or joy, abandoning desire, attachment, and fear."
        ),
        "medium": (
            "The Gītā portrays the *sthita-prajña* as an ideal seeker: "
            "calm amidst turmoil, free of likes and dislikes, with senses mastered, "
            "content in the Self alone. In [2:55–2:72], Krishna explains that such a one "
            "neither rejoices at gain nor laments at loss, and walks steadily toward liberation."
        ),
        "long": (
            "### Characteristics of the sthita-prajña\n"
            "- **[2:55]**: Abandons desires, satisfied in the Self alone.  \n"
            "- **[2:56]**: Not disturbed by sorrow, not overjoyed by pleasure, free from attachment, fear, anger.  \n"
            "- **[2:57–59]**: Moves among sense objects without attachment, senses disciplined, delighting in the Self.  \n"
            "- **[2:64–66]**: Self-controlled, peaceful, beyond agitation, fit for steadfast wisdom.  \n"
            "- **[2:70–72]**: Like the ocean—full yet undisturbed by rivers entering it—attains peace.\n\n"
            "Such a person lives in equanimity, detached yet engaged, and attains Brahman-nirvāṇa."
        ),
    },

    # --- Surrender: what it means ---
    "What does the Gita mean by surrender to the Lord?": {
        "short": (
            "Surrender (*śaraṇāgati*) is entrusting oneself wholly to Krishna—"
            "laying down egoic doership and relying on grace while still acting. "
            "Krishna’s pledge of refuge [18:66] and providential care [9:22] anchor this path; "
            "He welcomes all who turn to Him [9:31–32]."
        ),
        "medium": (
            "In the Gītā, surrender is not passivity but decisive trust. Krishna’s climactic call—"
            "“take refuge in Me alone; I will liberate you; do not grieve” [18:66]—"
            "resolves the tension between effort and control: act, but let go of ownership of results. "
            "Earlier He promises to carry what devotees lack and preserve what they have [9:22]; "
            "the door is open to everyone who turns to Him in faith [9:31–32]. "
            "For those still growing, He outlines a graded practice: fix the mind on Him; if not, practice; "
            "if not, work for His sake; if not, renounce the fruits [12:8–12]."
        ),
        "long": (
            "### What surrender is (and isn’t)\n"
            "Surrender (*śaraṇāgati*) is wholehearted refuge in the Divine. It is **not** inaction; "
            "it is acting fully while laying down the ego’s claim of “I am the doer.” "
            "Krishna’s final assurance—**“Take refuge in Me alone; I will free you from all sin; do not grieve.”** [18:66]—"
            "is the heart of the teaching.\n\n"
            "### Core verses to start with\n"
            "- **[18:66]** — Final instruction: complete refuge and fearlessness.  \n"
            "- **[9:22]** — “I carry what they lack and preserve what they have”: providence for the surrendered.  \n"
            "- **[9:31–32]** — Inclusivity: whoever turns to Him is uplifted.\n\n"
            "### A graded way into surrender (for everyday life)\n"
            "- **[12:8]**: Keep the mind fixed in Him.  \n"
            "- **[12:9]**: If not, keep practicing remembrance.  \n"
            "- **[12:10]**: If not, **work for His sake.**  \n"
            "- **[12:11–12]**: If not, **give up the fruits**—start with outcome-letting-go.\n\n"
            "### Living the teaching\n"
            "- Begin and end tasks with an inner offering.  \n"
            "- When anxiety spikes, recall the pledges of **[18:66]** and **[9:22]**.  \n"
            "- Keep acting skillfully, but place results at His feet; peace follows as bondage to outcomes loosens."
        ),
    },

    # --- Surrender: daily practice ---
    "How can one practice surrender in daily life?": {
        "short": (
            "Offer actions to the Lord, remember the pledges of refuge [18:66] and care [9:22], "
            "act wholeheartedly and release outcomes."
        ),
        "medium": (
            "Practice *śaraṇāgati* through small, steady moves: begin tasks with an inner offering; "
            "recall **[18:66]** when anxiety spikes and **[9:22]** when you feel unsupported; "
            "work skillfully yet relinquish doership and results. Use the graded steps in **[12:8–12]**: "
            "fix the mind, practice remembrance, work for Him, or—at minimum—give up the fruits."
        ),
        "long": (
            "### Daily ways to live surrender\n"
            "- **Morning resolve:** set an intention of refuge; dedicate the day to Him.  \n"
            "- **During work:** silently offer each task; keep a brief remembrance between meetings ([12:9–10]).  \n"
            "- **When worry rises:** lean on **[18:66]** (“I will free you; do not grieve”) and **[9:22]** (“I carry and preserve”).  \n"
            "- **Outcome release:** finish actions by placing results at His feet ([12:11–12]).  \n"
            "- **Evening recall:** review the day as given and returned.\n\n"
            "Surrender grows by repetition: keep acting, but let the heart rest in refuge."
        ),
    },
}

def seed():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    inserted = 0
    updated = 0

    for qtext, ansmap in ANSWERS.items():
        # ensure question exists
        cur.execute("SELECT id FROM questions WHERE question_text=?", (qtext,))
        row = cur.fetchone()
        if row:
            qid = row[0]
        else:
            cur.execute(
                "INSERT INTO questions (question_text, micro_topic_id, intent, priority) VALUES (?, ?, ?, ?)",
                (qtext, None, "canonical", 1),
            )
            qid = cur.lastrowid
            inserted += 1

        for tier, text in ansmap.items():
            cur.execute(
                "SELECT id FROM answers WHERE question_id=? AND length_tier=?",
                (qid, tier),
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE answers SET answer_text=? WHERE question_id=? AND length_tier=?",
                    (text, qid, tier),
                )
                updated += 1
            else:
                cur.execute(
                    "INSERT INTO answers (question_id, length_tier, answer_text) VALUES (?, ?, ?)",
                    (qid, tier, text),
                )
                inserted += 1

    conn.commit()
    conn.close()
    print(f"[seed_answers] inserted {inserted}, updated {updated}, total {len(ANSWERS)} questions")

if __name__ == "__main__":
    seed()
