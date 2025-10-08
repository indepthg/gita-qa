# app/seed_answers.py  (REPLACE FILE)

import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

# Canonical answers in the agreed styles:
# - SHORT/MEDIUM = narrative paragraphs (varied)
# - LONG = structured sections (only when helpful)
ANSWERS = {
  # ---------------------------
  # SURRENDER / REFUGE (1001)
  # ---------------------------
  "What does the Gītā mean by surrender to the Lord?": {
    "short": (
      "Surrender (*śaraṇāgati*) is entrusting oneself wholly to Krishna—"
      "releasing the ego’s claim of control and relying on divine grace. "
      "It culminates in the assurance of freedom in [18:66] and the promise of care in [9:22]."
    ),
    "medium": (
      "The Gītā treats surrender not as passivity but as clear, active trust. "
      "Krishna’s climactic instruction—“Abandon all dharmas and take refuge in Me alone; "
      "I will liberate you from all sins; do not grieve” [18:66]—invites Arjuna to lay down "
      "the burden of doership while still acting. Earlier He promises to safeguard those who "
      "are steadfast in devotion: “I carry what they lack and preserve what they have” [9:22]. "
      "This path is radically inclusive: even those seen as fallen are lifted when devotion is firm [9:31–32]."
    ),
    # Long = a different section set (to avoid cookie-cutter)
    "long": (
      "### In one line\n"
      "Entrust everything to the Divine and act freely—grace carries what the ego cannot.  \n\n"
      "### Where Krishna says it\n"
      "- Final call to refuge: **“Take refuge in Me alone”** — [18:66]  \n"
      "- Assurance of protection: **“I carry what they lack…”** — [9:22]  \n"
      "- Radical inclusivity: **all who turn to Him are uplifted** — [9:31–32]\n\n"
      "### How to live it\n"
      "- Begin tasks with an inner offering and end them the same way.  \n"
      "- When anxiety rises, remember the pledges in [18:66] and [9:22].  \n"
      "- Keep acting, but place outcomes at the Lord’s feet.  \n\n"
      "### Why it matters\n"
      "Surrender resolves the strain between effort and control. "
      "It cuts the root of bondage (egoic doership) and opens the heart to peace and liberation."
    )
  },

  "How can one practice surrender in daily life?": {
    "short": (
      "Offer each action to the Divine, recall the pledge of refuge in [18:66], "
      "and trust the promise of care in [9:22]. Act fully—release outcomes."
    ),
    "medium": (
      "Practice *śaraṇāgati* by consciously offering food, work, and speech to Krishna; "
      "start and end the day with an inner act of refuge; when worry appears, remember "
      "the assurances in [18:66] and [9:22]. This is not withdrawal but freedom in action."
    ),
    "long": (
      "### Daily practice of surrender\n"
      "- **Conscious offering:** dedicate tasks, meetings, and meals to the Lord.  \n"
      "- **Remember the promise:** hold [18:66] and [9:22] when fear peaks.  \n"
      "- **Let go of results:** act wholeheartedly, leave fruit to Him.  \n"
      "- **Steady trust:** return to refuge in quiet pauses through the day."
    )
  },

  "Which verses teach about surrender?": {
    "short": "Primary: [18:66], [9:22], [9:31–32]. Related practice ladder: [12:8–12].",
    "medium": (
      "**Primary:** [18:66] (final call to refuge), [9:22] (assurance of care), [9:31–32] "
      "(inclusivity). **Related:** [12:8–12] outlines a graded approach to devotion and surrender."
    ),
    "long": (
      "### Core verses\n"
      "- **[18:66]** — Final instruction: complete refuge.  \n"
      "- **[9:22]** — Divine preservation and provision.  \n"
      "- **[9:31–32]** — Everyone who turns to Him is uplifted.  \n\n"
      "### Related practice\n"
      "- **[12:8–12]** — A step-down ladder for cultivating surrender."
    )
  },

  # ---------------------------
  # STHITA-PRAJÑA (1002)
  # ---------------------------
  "What is a sthita-prajña in the Bhagavad Gītā?": {
    "short": (
      "A *sthita-prajña* is a person of steady wisdom—free from cravings, even-minded in gain and loss, "
      "and resting in the Self. Krishna’s portrait spans [2:55–72]."
    ),
    "medium": (
      "When Arjuna asks about the marks of the realized one [2:54], Krishna describes a sage who has let go of "
      "selfish desires and is content in the Self [2:55], remains unshaken by pleasure or pain [2:56], "
      "and withdraws the senses like a tortoise [2:58]. He moves among objects with discipline, gaining serenity "
      "[2:64–65], and is steady like an ocean filled yet unmoved [2:70]. This is freedom in the midst of life."
    ),
    # Long = the styled version we agreed to
    "long": (
      "### What is a Sthita-prajña?\n"
      "The term means “one of steady wisdom” — a sage whose understanding is firm and not shaken by desire or distress.\n\n"
      "### Where is it described?\n"
      "Arjuna asks in [2:54] about the marks of such a person. Krishna replies in [2:55–72], giving one of the Gītā’s "
      "most celebrated portraits of spiritual maturity.\n\n"
      "### Key Qualities (bulleted)\n"
      "- Free from cravings, content in the Self alone ([2:55])  \n"
      "- Even-minded in pleasure and pain, fearless and anger-free ([2:56])  \n"
      "- Withdraws the senses like a tortoise when needed ([2:58])  \n"
      "- Moves in the world unattached, gaining serenity and clarity ([2:64–65])  \n"
      "- Stands firm like the ocean filled by rivers, yet unmoved ([2:70])\n\n"
      "### Essence (takeaway)\n"
      "The *sthita-prajña* is not a renunciate withdrawn from life, but one who acts without bondage — "
      "the inner freedom and peace that is the goal of yoga ([2:71–72])."
    )
  },

  "What are the main qualities of a sthita-prajña?": {
    "short": "Desirelessness [2:55], equanimity [2:56], sense-control [2:58], serene discipline [2:64–65], deep stability [2:70], peace in the Self [2:71–72].",
    "medium": (
      "Freedom from cravings [2:55]; even-mindedness amid joy and sorrow [2:56]; tortoise-like "
      "withdrawal of senses [2:58]; movement in the world without attachment or aversion, gaining serenity [2:64–65]; "
      "stability like an ocean into which rivers flow [2:70]; peace beyond clinging [2:71–72]."
    ),
    "long": (
      "### Qualities at a glance\n"
      "- Desirelessness and contentment in the Self — [2:55]  \n"
      "- Equanimity in all dualities — [2:56]  \n"
      "- Sense-control without repression — [2:58–59]  \n"
      "- Serene engagement with the world — [2:64–65]  \n"
      "- Unmoved like the ocean — [2:70]  \n"
      "- Peace and freedom in Brahman — [2:71–72]"
    )
  },

  "Where does the Gītā describe the sthita-prajña?": {
    "short": "Asked in [2:54]; answered in [2:55–72].",
    "medium": "See [2:54–72] — the classic portrait of steady wisdom.",
    "long": (
      "### Where to read\n"
      "- Question: **[2:54]**  \n"
      "- Description: **[2:55–72]**  \n"
      "Start with [2:55–57] for core marks, [2:58–65] for practice of mind, and [2:66–72] for the fruit of peace."
    )
  }
}

# Upsert-with-update: if an answer exists for (question_id, tier), UPDATE it; otherwise INSERT.
SQL_FIND_QID = "SELECT id FROM questions WHERE question_text = ? LIMIT 1;"
SQL_FIND_A   = "SELECT 1 FROM answers WHERE question_id=? AND length_tier=? LIMIT 1;"
SQL_INS_A    = "INSERT INTO answers (question_id, length_tier, answer_text) VALUES (?, ?, ?);"
SQL_UPD_A    = "UPDATE answers SET answer_text=? WHERE question_id=? AND length_tier=?;"

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_ins, total_upd, missing_q = 0, 0, 0

    for q_text, tiers in ANSWERS.items():
        row = cur.execute(SQL_FIND_QID, (q_text,)).fetchone()
        if not row:
            print(f"[seed_answers] SKIP (question not found): {q_text}")
            missing_q += 1
            continue
        qid = row[0]
        for tier, content in tiers.items():
            exists = cur.execute(SQL_FIND_A, (qid, tier)).fetchone()
            if exists:
                cur.execute(SQL_UPD_A, (content, qid, tier))
                total_upd += cur.rowcount
            else:
                cur.execute(SQL_INS_A, (qid, tier, content))
                total_ins += cur.rowcount

    con.commit()
    con.close()
    print(f"[seed_answers] inserted {total_ins}, updated {total_upd}, questions_missing {missing_q}")

if __name__ == "__main__":
    main()
