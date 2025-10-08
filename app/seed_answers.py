# app/seed_answers.py
import os, sqlite3

DB_PATH = os.getenv("DB_PATH", "/data/gita.db")

# Canonical Q→A seeds (Short / Medium / Long). Use [chapter:verse] or ranges [12:8–12].
ANSWERS = {
    # =========================
    # SURRENDER / REFUGE
    # =========================
    "What does the Gītā mean by surrender to the Lord?": {
        "short": (
            "Surrender (*śaraṇāgati*) is entrusting oneself wholly to Krishna—"
            "laying down egoic doership and relying on grace **while still acting**. "
            "Its heart is His pledge of refuge [18:66] and providential care [9:22]; "
            "the door is open to all who turn to Him [9:31–32]."
        ),
        "medium": (
            "In the Gītā, surrender is decisive trust, not passivity. Krishna’s climactic call—"
            "**“Take refuge in Me alone; I will free you; do not grieve.”** [18:66]—"
            "resolves the tension between effort and control: act, but lay down ownership of results. "
            "He promises to *carry what devotees lack and preserve what they have* [9:22], and assures that "
            "whoever turns to Him is uplifted [9:31–32]. For gradual practice He gives a ladder: fix the mind, "
            "if not practice, if not **work for His sake**, or at least renounce the fruits [12:8–12]."
        ),
        "long": (
            "### What surrender is (and isn’t)\n"
            "Surrender (*śaraṇāgati*) is wholehearted refuge in the Divine. It is **not** inaction; "
            "it is acting fully while laying down the ego’s “I am the doer.” "
            "Krishna’s final assurance—**“Take refuge in Me alone; I will free you from all sin; do not grieve.”** [18:66]—"
            "is the living center of the teaching.\n\n"
            "### Core verses to start with\n"
            "- **[18:66]** — Final instruction: complete refuge and fearlessness.  \n"
            "- **[9:22]** — “I carry what they lack and preserve what they have.”  \n"
            "- **[9:31–32]** — Inclusivity: whoever turns to Him is uplifted.\n\n"
            "### A graded way into surrender\n"
            "- **[12:8]** Keep the mind fixed in Him.  \n"
            "- **[12:9]** If not, keep practicing remembrance.  \n"
            "- **[12:10]** If not, **work for His sake.**  \n"
            "- **[12:11–12]** If not, **give up the fruits**—begin with outcome-letting-go.\n\n"
            "### Living the teaching\n"
            "Begin and end tasks with an inner offering; when anxiety rises, recall **[18:66]** and **[9:22]**; "
            "keep acting skillfully but place results at His feet—peace follows as bondage to outcomes loosens."
        )
    },

    "How can one practice surrender in daily life?": {
        "short": (
            "Offer actions to the Lord; remember refuge [18:66] and care [9:22]; "
            "act wholeheartedly and release outcomes."
        ),
        "medium": (
            "Practice *śaraṇāgati* in small, steady ways: begin tasks with an inner offering; "
            "recall **[18:66]** when fear spikes and **[9:22]** when you feel unsupported; "
            "work skillfully yet relinquish doership and results. Follow the graded steps **[12:8–12]**: "
            "fix the mind, practice remembrance, work for Him, or—at minimum—give up the fruits."
        ),
        "long": (
            "### Daily ways to live surrender\n"
            "- **Morning resolve:** set an intention of refuge; dedicate the day to Him.  \n"
            "- **During work:** silently offer each task; brief remembrance between meetings ([12:9–10]).  \n"
            "- **When worry rises:** lean on **[18:66]** (“I free you; do not grieve”) and **[9:22]** (“I carry and preserve”).  \n"
            "- **Outcome release:** close actions by placing results at His feet ([12:11–12]).  \n"
            "- **Evening recall:** review the day as given and returned.\n\n"
            "Surrender grows by repetition: keep acting, but let the heart rest in refuge."
        )
    },

    "Which verses teach about surrender?": {
        "short": "Primary: **[18:66]**, **[9:22]**, **[9:31–32]**. Related: **[12:8–12]** (graded practice).",
        "medium": (
            "**Primary:** [18:66] final call to refuge; [9:22] divine providence; [9:31–32] inclusivity.  "
            "**Related:** [12:8–12] gives a step-down path to surrender for everyday life."
        ),
        "long": (
            "### Core\n"
            "- **[18:66]** — Complete refuge and fearlessness.  \n"
            "- **[9:22]** — Preservation and provision for the devoted.  \n"
            "- **[9:31–32]** — All who turn to Him are uplifted.  \n\n"
            "### Related practice\n"
            "- **[12:8–12]** — A graded approach: remembrance → practice → work for Him → give up the fruits."
        )
    },

    # =========================
    # STHITA-PRAJÑĀ (2:54–72)
    # =========================
    "What is a sthita-prajña in the Bhagavad Gītā?": {
        "short": (
            "A *sthita-prajñā* is a person of steady wisdom—content in the Self, even-minded, "
            "and free from craving and fear. Krishna’s portrait spans **[2:55–72]**."
        ),
        "medium": (
            "Asked in **[2:54]**, Krishna describes one who has given up selfish desires and is satisfied in the Self **[2:55]**, "
            "remains unshaken by pleasure and pain **[2:56]**, withdraws the senses like a tortoise **[2:58]**, "
            "moves in the world with discipline **[2:64–65]**, and is steady like an ocean **[2:70]**—"
            "peace and freedom follow **[2:71–72]**."
        ),
        "long": (
            "### Where it appears\n"
            "Arjuna asks about the realized one in **[2:54]**; Krishna answers in **[2:55–72]**.\n\n"
            "### Key qualities\n"
            "- Content in the Self, desireless — **[2:55]**  \n"
            "- Even-minded in pleasure and pain — **[2:56]**  \n"
            "- Sense-control without repression — **[2:58–59]**  \n"
            "- Serenity through disciplined engagement — **[2:64–65]**  \n"
            "- Deep stability: ocean metaphor — **[2:70]**  \n"
            "- Peace/liberation — **[2:71–72]**\n\n"
            "### Essence\n"
            "Freedom in the midst of life: acts without bondage, rests in the Self."
        )
    },

    "What are the main qualities of a sthita-prajña?": {
        "short": (
            "Desirelessness **[2:55]**, equanimity **[2:56]**, sense-control **[2:58–59]**, "
            "serenity in action **[2:64–65]**, ocean-like stability **[2:70]**, peace **[2:71–72]**."
        ),
        "medium": (
            "Gita lists the marks: giving up cravings and settling in the Self **[2:55]**; "
            "unmoved by dualities **[2:56]**; senses disciplined **[2:58–59]**; "
            "moving among objects without attachment or aversion **[2:64–65]**; "
            "steady like the ocean **[2:70]**; finally, peace and freedom **[2:71–72]**."
        ),
        "long": (
            "### Snapshot of qualities\n"
            "- Desirelessness and inner contentment — **[2:55]**  \n"
            "- Equanimity amid gain/loss — **[2:56]**  \n"
            "- Mastery of the senses — **[2:58–59]**  \n"
            "- Serene engagement with the world — **[2:64–65]**  \n"
            "- Unmoved like the ocean — **[2:70]**  \n"
            "- Peace rooted in Self-knowledge — **[2:71–72]**"
        )
    },

    "Where does the Gītā describe the sthita-prajña?": {
        "short": "Asked in **[2:54]**; answered in **[2:55–72]**.",
        "medium": "Read **[2:54–72]**—a complete portrait of steady wisdom.",
        "long": (
            "### Reading path\n"
            "- Question: **[2:54]**  \n"
            "- Description: **[2:55–72]**  \n"
            "Start **[2:55–57]** for core marks, **[2:58–65]** for practice of mind, **[2:66–72]** for the fruit of peace."
        )
    },

    # =========================
    # KARMA / BHAKTI / JÑĀNA
    # =========================
    "What is Karma-yoga in the Gītā?": {
        "short": (
            "Act skillfully without attachment to results—offer the action to the Divine. "
            "See **[2:47]**, **[3:19]**, **[3:30]**, **[5:10]**."
        ),
        "medium": (
            "Karma-yoga purifies by **doing** without clinging. Perform your role **[3:19]**, "
            "offer actions to the Lord **[3:30]**, give up ownership of results **[2:47]**, and remain untouched like a lotus "
            "by dedicating work to Him **[5:10]**."
        ),
        "long": (
            "### Core lines\n"
            "- **[2:47]** — Your right is to action, not to the fruits.  \n"
            "- **[3:19]** — Perform duty without attachment.  \n"
            "- **[3:30]** — Dedicate all actions to Me; fight without fever.  \n"
            "- **[5:10]** — He who offers acts to Brahman is untainted, like a lotus leaf in water.\n\n"
            "Karma-yoga turns daily work into a practice that loosens ego and ripens the heart."
        )
    },

    "What is Bhakti in the Gītā?": {
        "short": "Loving devotion to the Lord that purifies and leads to union. See **[9:22]**, **[12:13–20]**, **[18:65–66]**.",
        "medium": (
            "Bhakti is wholehearted love and refuge. The Lord carries and preserves for the devoted **[9:22]**; "
            "He praises the devotee’s qualities **[12:13–20]**; the path culminates in loving remembrance and surrender "
            "**[18:65–66]**."
        ),
        "long": (
            "### Marks of the devotee\n"
            "- **[12:13–20]** — Kind, fearless, forgiving, even-minded, without hatred; such devotees are dear to Him.  \n"
            "### Relationship and promise\n"
            "- **[9:22]** — Providential care; **[18:65–66]** — loving remembrance and final refuge.\n\n"
            "Bhakti integrates head, heart, and hand: love, knowledge, and action meet in surrender."
        )
    },

    "What is Jñāna-yoga according to the Gītā?": {
        "short": "Knowledge that discerns the Self (ātman) from the not-Self; see **[2:16–25]**, **[4:34–38]**, **[13:1–3]**.",
        "medium": (
            "Jñāna-yoga is insight into the imperishable Self. The real is not destroyed **[2:16–17]**; "
            "the Self is unborn, eternal **[2:20]**; knowledge burns karma **[4:37–38]**; "
            "knower, field, and Lord are explained **[13:1–3]**."
        ),
        "long": (
            "### Themes\n"
            "- **[2:16–25]** — Nature of the Self: unborn, undying, all-pervading.  \n"
            "- **[4:34–38]** — Humble inquiry into truth; knowledge purifies.  \n"
            "- **[13:1–3]** — The field and the knower; the Lord as knower in all.\n\n"
            "Jñāna clarifies: it ends confusion, turning action into freedom."
        )
    },

    "Which path is better—Bhakti, Karma, or Jñāna?": {
        "short": "All are valid; the Gītā harmonizes them—love, knowledge, and selfless action meet in surrender (**[12:8–12]**, **[18:66]**).",
        "medium": (
            "The Gītā offers a **synthesis**. Karma purifies through duty without attachment **[3:19]**; "
            "Jñāna illumines the Self **[2:20]**; Bhakti gives refuge and intimacy **[12:13–20]**, **[18:65–66]**. "
            "Krishna provides a graded path **[12:8–12]** to meet seekers where they are."
        ),
        "long": (
            "### A harmonious path\n"
            "- **Karma** trains the hands: selfless action **[2:47]**, **[3:19]**.  \n"
            "- **Jñāna** clears the head: the imperishable Self **[2:16–25]**, **[4:34–38]**.  \n"
            "- **Bhakti** opens the heart: qualities and refuge **[12:13–20]**, **[18:65–66]**.\n\n"
            "The Gītā invites integration: act, know, and love—centered in surrender."
        )
    },

    # =========================
    # MEDITATION / MIND
    # =========================
    "How does the Gītā teach meditation (dhyāna)?": {
        "short": "Seat, posture, discipline, and focus on the Self/Lord—see **[6:10–15]**, with mind-handling in **[6:26]**.",
        "medium": (
            "Meditate in a clean, steady seat **[6:11]**, with upright posture **[6:13]**, "
            "moderation in food/sleep **[6:16–17]**, and the mind fixed in the Self/Lord **[6:14–15]**. "
            "When the mind wanders, bring it back gently **[6:26]**."
        ),
        "long": (
            "### Steps\n"
            "- **[6:10–12]** — Quiet place, steady seat.  \n"
            "- **[6:13–14]** — Upright posture; calm, devoted focus.  \n"
            "- **[6:16–17]** — Moderation.  \n"
            "- **[6:26]** — Bring the roaming mind back with patience.\n\n"
            "Meditation stabilizes insight and supports Karma-yoga and Bhakti alike."
        )
    },

    # =========================
    # DESIRE / ANGER (LADDER OF FALL)
    # =========================
    "What is the Gītā’s ‘ladder of fall’ from desire to ruin?": {
        "short": "From contemplation → desire → anger → delusion → memory loss → loss of reason → ruin **[2:62–63]**.",
        "medium": (
            "Dwelling on sense-objects breeds desire; desire thwarted becomes anger; anger gives rise to delusion; "
            "delusion to loss of memory; memory lost, reason is ruined; and one falls **[2:62–63]**. "
            "The cure is disciplined movement among objects and remembrance **[2:64–65]**."
        ),
        "long": (
            "### The sequence (to watch in real time)\n"
            "Contemplation → desire → anger → delusion → memory loss → loss of reason → downfall **[2:62–63]**.  \n"
            "### Remedy\n"
            "Move among objects with discipline **[2:64]**; serenity restores insight **[2:65]**; "
            "freedom from craving begins the healing **[2:55]**."
        )
    },

    # =========================
    # FOOD / GUNAS / FAITH
    # =========================
    "What food should I eat according to the Gītā?": {
        "short": "Prefer **sāttvic** foods—fresh, light, life-giving; avoid **rājasic** (over-spicy) and **tāmasic** (stale)—**[17:8–10]**.",
        "medium": (
            "The Gītā classifies food by the three guṇas: **sāttvic**—fresh, wholesome, increasing life and clarity **[17:8]**; "
            "**rājasic**—bitter, sour, salty, very hot, producing pain and disease **[17:9]**; "
            "**tāmasic**—stale, tasteless, putrid **[17:10]**."
        ),
        "long": (
            "### Food and the mind\n"
            "- **Sāttvic [17:8]** — increases life, purity, strength, health, happiness.  \n"
            "- **Rājasic [17:9]** — very hot/acidic/salty; leads to pain, grief.  \n"
            "- **Tāmasic [17:10]** — stale or impure, dulling consciousness.\n\n"
            "Choose sāttvic as a rule; take rājasic sparingly; avoid tāmasic."
        )
    },

    "What are the three guṇas?": {
        "short": "Sattva (clarity), Rajas (activity), Tamas (inertia) — bind beings in different ways **[14:5–9]**.",
        "medium": (
            "Sattva is luminous and buoyant, binding by attachment to happiness and knowledge **[14:6]**; "
            "Rajas is passion and restlessness, binding by attachment to action **[14:7]**; "
            "Tamas is inertia and delusion, binding by negligence **[14:8–9]**."
        ),
        "long": (
            "### Signs and outcomes\n"
            "- Rise of **Sattva**: light, clarity, health **[14:11]**.  \n"
            "- Rise of **Rajas**: greed, agitation, feverish activity **[14:12]**.  \n"
            "- Rise of **Tamas**: darkness, inertia, confusion **[14:13]**.  \n"
            "Transcending the three by devotion and knowledge leads to freedom **[14:20–26]**."
        )
    },

    "What kind of faith (śraddhā) do people have?": {
        "short": "Faith follows one’s guṇa: sāttvic, rājasic, tāmasic **[17:2–4]**.",
        "medium": (
            "“A person is their faith” **[17:3]**. Sāttvic faith seeks the Divine; rājasic seeks power or benefit; "
            "tāmasic is deluded or harmful **[17:2–4]**."
        ),
        "long": (
            "### Faith mirrors the mind’s composition\n"
            "By purifying life (food, action, charity) we refine faith **[17:8–22]**; "
            "offerings done without expectation, in the right spirit, become sāttvic **[17:11–14, 17–22]**."
        )
    },

    # =========================
    # ATMAN / ALWAYS REAL
    # =========================
    "What then is that which is always real?": {
        "short": "The imperishable Self (Ātman) pervading all is **indestructible** **[2:17]**.",
        "medium": (
            "That which pervades all is indestructible; none can bring about the destruction of the imperishable Self **[2:17]**. "
            "The Self is unborn and undying **[2:20]**."
        ),
        "long": (
            "### Nature of the Self\n"
            "- **[2:17]** — The pervading reality is indestructible.  \n"
            "- **[2:20]** — Unborn, eternal, not slain when the body is slain.  \n"
            "- **[2:23–25]** — Not cut, not burnt, stable, all-pervading.\n\n"
            "Knowing this frees one from fear and grief."
        )
    },

    # =========================
    # ACTION WITHOUT ATTACHMENT
    # =========================
    "How do I act without attachment to results?": {
        "short": "Do your work as worship; give up ownership of the fruit — **[2:47]**, **[3:19]**, **[3:30]**, **[5:10]**.",
        "medium": (
            "Hold **[2:47]** as your compass: act, but don’t grasp the fruit. Perform duty steadily **[3:19]**; "
            "dedicate acts to the Lord **[3:30]**; remain untouched like a lotus by offering work to Him **[5:10]**."
        ),
        "long": (
            "### Practice notes\n"
            "- Choose clarity over outcomes before you begin (intention).  \n"
            "- Work wholeheartedly; keep remembrance while acting **[3:30]**.  \n"
            "- Consciously release the result at completion **[2:47]**.  \n"
            "- Let equanimity be your success metric **[2:48]**."
        )
    },
}

# ---- Seeder ----
SQL_FIND_Q = "SELECT id FROM questions WHERE question_text=? LIMIT 1;"
SQL_INS_Q  = "INSERT INTO questions (question_text, micro_topic_id, intent, priority) VALUES (?, ?, ?, ?);"
SQL_FIND_A = "SELECT 1 FROM answers WHERE question_id=? AND length_tier=? LIMIT 1;"
SQL_UPD_A  = "UPDATE answers SET answer_text=? WHERE question_id=? AND length_tier=?;"
SQL_INS_A  = "INSERT INTO answers (question_id, length_tier, answer_text) VALUES (?, ?, ?);"

def seed():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    inserted, updated, q_created = 0, 0, 0

    for qtext, tiers in ANSWERS.items():
        row = cur.execute(SQL_FIND_Q, (qtext,)).fetchone()
        if row:
            qid = row[0]
        else:
            # Safe defaults if questions aren’t preseeded
            cur.execute(SQL_INS_Q, (qtext, 9999, "canonical", 1))
            qid = cur.lastrowid
            q_created += 1

        for tier, content in tiers.items():
            if cur.execute(SQL_FIND_A, (qid, tier)).fetchone():
                cur.execute(SQL_UPD_A, (content, qid, tier))
                updated += cur.rowcount
            else:
                cur.execute(SQL_INS_A, (qid, tier, content))
                inserted += cur.rowcount

    con.commit()
    con.close()
    print(f"[seed_answers] inserted {inserted}, updated {updated}, questions_created {q_created}, total_topics {len(ANSWERS)}")

if __name__ == "__main__":
    seed()
