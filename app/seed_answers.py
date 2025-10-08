# app/seed_answers.py
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

# Canonical answers (hybrid formatting you approved).
ANSWERS = {
  # Surrender — short/medium/long
  "What does the Gītā mean by surrender to the Lord?": {
    "short": """Surrender in the Gītā means entrusting oneself completely to Krishna, letting go of ego and the burden of control. In [18:66], He assures freedom from sin and grief for those who take refuge in Him; [9:22] promises divine care.""",

    "medium": """At the close of the Gītā, Krishna gives a decisive teaching: “Abandon all dharmas and take refuge in Me alone. I shall liberate you from all sins; do not grieve” [18:66]. This is not a rejection of action but a release from clinging to outcomes. Earlier, “To those ever steadfast in devotion, I carry what they lack and preserve what they have” [9:22]. Refuge is inclusive—“even those considered sinful, when devoted, quickly become righteous” [9:31–32]. Practically, surrender is wholehearted action with inward offering to the Divine—trust replacing anxiety, grace replacing egoic burden.""",

    "long": """<section>
<p><strong>Surrender / Refuge (śaraṇāgati)</strong></p>
<p><em>Key verses:</em> [18:66], [9:22], [9:31–32]</p>
<p>Surrender means yielding the ego’s claim of doership and relying on divine grace. It is active trust, not passivity: we continue to act, placing results at the Lord’s feet.</p>
<ul>
  <li><strong>Where it’s taught:</strong> Final instruction [18:66]; assurance of care [9:22]; radical inclusivity [9:31–32].</li>
  <li><strong>Why it matters:</strong> It resolves the tension between effort and grace, cutting the root of anxiety and bondage.</li>
  <li><strong>Practice:</strong> Offer actions, remember the promise in difficulty, and cultivate the inner stance “Not I, but Thou.”</li>
</ul>
<p><strong>Essence:</strong> The Gītā places surrender at the heart of the path because it frees the seeker into peace and liberation.</p>
</section>"""
  },

  # Sthita-prajña — short/medium/long
  "What is a sthita-prajña in the Bhagavad Gītā?": {
    "short": """A sthita-prajña is one whose wisdom is firmly established, unshaken by desire or disturbance. Krishna’s portrait in [2:55–72] shows freedom from craving, equanimity in pleasure and pain, mastery of the senses, and inner peace grounded in the Self.""",

    "medium": """Arjuna asks in [2:54] for the marks of the person of steady wisdom. Krishna replies: desirelessness and contentment in the Self [2:55]; even-mindedness amid joy and grief [2:56]; sense-control like a tortoise withdrawing its limbs [2:58]; serene movement among objects with discipline [2:64–65]; stability like an ocean filled yet unmoved [2:70]. This is not withdrawal from life but freedom in life—the sage acts without bondage, resting in inner clarity.""",

    "long": """<section>
<p><strong>Sthita-prajña (Person of steady wisdom)</strong></p>
<p><em>Key verses:</em> [2:54–72]</p>
<p>Krishna describes the realized person as free of selfish craving [2:55], unshaken in sorrow or joy [2:56], and capable of withdrawing the senses when needed [2:58], not by repression but by a higher taste [2:59].</p>
<ul>
  <li><strong>Equanimity:</strong> moves among objects without attachment/aversion, gaining serenity [2:64–65].</li>
  <li><strong>Images:</strong> lamp in a windless place; ocean filled yet unmoved [2:67, 2:70].</li>
  <li><strong>Fruit:</strong> peace through renunciation of clinging and ego [2:71–72].</li>
</ul>
<p><strong>Essence:</strong> Not escape, but inner mastery—living and acting in freedom.</p>
</section>"""
  },

  # Extras for the other seeded questions (very brief)
  "How can one practice surrender in daily life?": {
    "short": """Offer each action to the Divine, recall [18:66] in hardship, and cultivate trust as in [9:22]. Act fully, release outcomes—let grace carry what the ego cannot.""",
    "medium": """Practice surrender by beginning and ending the day with an inner act of refuge; offer food, work, and speech as service; when anxiety rises, remember the promises [18:66], [9:22]. Keep acting, but inwardly lay results at the Lord’s feet.""",
    "long": """Surrender is lived moment to moment: consciously offer actions, rely on the promise of care [9:22], and relinquish the anxious claim of doership in light of [18:66]. It is steady trust, not passivity; courage, not escape."""
  },
  "Which verses teach about surrender?": {
    "short": """[18:66], [9:22], [9:31–32] (see also [12:8–12] for graded approach).""",
    "medium": """Primary verses: [18:66] (final call to refuge), [9:22] (assurance of care), [9:31–32] (inclusivity). Related: [12:8–12] (graded path).""",
    "long": """Primary: [18:66], [9:22], [9:31–32]. Related practice: [12:8–12]."""
  },
  "What are the main qualities of a sthita-prajña?": {
    "short": """Desirelessness [2:55], even-mindedness [2:56], sense-control [2:58], serene discipline [2:64–65], deep stability [2:70], peace in Self [2:71–72].""",
    "medium": """Freedom from cravings [2:55], equanimity in joy/sorrow [2:56], tortoise-like sense-withdrawal [2:58], disciplined movement among objects [2:64–65], steady like the ocean [2:70], culminating in peace [2:71–72].""",
    "long": """The sthita-prajña lives desire-free and even-minded [2:55–56], masters the senses [2:58–59], moves with disciplined serenity [2:64–65], stands firm like an ocean [2:70], and abides in peace beyond clinging [2:71–72]."""
  },
  "Where does the Gītā describe the sthita-prajña?": {
    "short": """Arjuna asks in [2:54]; Krishna answers in [2:55–72].""",
    "medium": """The portrait spans [2:54–72]: question at [2:54]; qualities through [2:55–72] (desirelessness, equanimity, sense-control, serenity, peace).""",
    "long": """See [2:54–72]. Begin with [2:55–57] for core marks, [2:58–65] for practice and mind, [2:66–72] for fruits and steady peace."""
  }
}

UPSERT_Q = "SELECT id FROM questions WHERE question_text = ? LIMIT 1"
UPSERT_A = """
INSERT INTO answers (question_id, length_tier, answer_text)
SELECT ?, ?, ?
WHERE NOT EXISTS (
  SELECT 1 FROM answers WHERE question_id = ? AND length_tier = ?
);
"""

def main():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total = 0
    for q_text, tiers in ANSWERS.items():
        row = cur.execute(UPSERT_Q, (q_text,)).fetchone()
        if not row:
            print(f"[seed_answers] SKIP (question not found): {q_text}")
            continue
        qid = row[0]
        for tier, content in tiers.items():
            cur.execute(UPSERT_A, (qid, tier, content, qid, tier))
            total += cur.rowcount
    con.commit()
    print(f"[seed_answers] upserted {total} answer rows")
    con.close()

if __name__ == "__main__":
    main()
