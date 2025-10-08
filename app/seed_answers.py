# app/seed_answers.py
import os, sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/gita.db")

# Canonical answers in the agreed styles:
# - SHORT/MEDIUM = narrative paragraphs (varied)
# - LONG = structured sections (chosen per topic)

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
    # Long = "In one line / Where / How / Why" (practice theme)
    "long": (
      "### In one line\n"
      "Entrust everything to the Divine and act freely—grace carries what the ego cannot.\n\n"
      "### Where Krishna says it\n"
      "- Final call to refuge: **“Take refuge in Me alone”** — [18:66]\n"
      "- Assurance of protection: **“I carry what they lack…”** — [9:22]\n"
      "- Radical inclusivity: **all who turn to Him are uplifted** — [9:31–32]\n\n"
      "### How to live it\n"
      "- Begin tasks with an inner offering and end them the same way.\n"
      "- When anxiety rises, remember the pledges in [18:66] and [9:22].\n"
      "- Keep acting, but place outcomes at the Lord’s feet.\n\n"
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
      "- **Conscious offering:** dedicate tasks, meetings, and meals to the Lord.\n"
      "- **Remember the promise:** hold [18:66] and [9:22] when fear peaks.\n"
      "- **Let go of results:** act wholeheartedly, leave fruit to Him.\n"
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
      "- **[18:66]** — Final instruction: complete refuge.\n"
      "- **[9:22]** — Divine preservation and provision.\n"
      "- **[9:31–32]** — Everyone who turns to Him is uplifted.\n\n"
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
      "selfish desires and is content in the Self
