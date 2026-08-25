# The Insider

> Version: 0.2.0
> Description: Диалоговый агент для вытягивания экспертизы и упаковки в контент.
> Проводит STARRI-интервью с экспертом, маппит историю на аудиторию/формат,
> генерирует черновики: Telegram-пост, заявку на доклад, кейс.
>
> Как использовать: открой проект → вызови /init → /extract → /map → /generate

---

## Quick Reference

```
┌──────────┐   ┌──────────┐   ┌────────┐   ┌──────────────┐
│ /init    │ → │ /extract │ → │ /map   │ → │ /generate    │
│ 1 раз    │   │          │   │        │   │              │
└──────────┘   └──────────┘   └────────┘   └──────────────┘
```

`/setup` — то же, что `/init`, но для повторной настройки (переконфигурация).

---

## Directory Structure

```
the-insider/
├── business/
│   ├── dna.yaml              # Business DNA (Layer 0)
│   └── content_map.yaml      # Content Map (Layer 3)
├── experts/
│   └── profiles/             # Expert profiles (my_data/)
├── stories/
│   ├── templates/
│   │   └── story.md
│   └── my_data/              # STARRI stories (my_data/)
├── artifacts/
│   ├── templates/
│   │   ├── telegram_post.md
│   │   ├── talk_proposal.md
│   │   └── case_study.md
│   └── my_data/              # Generated artifacts (my_data/)
├── config/
│   └── protocol.md            # Interview protocol
├── SKILL.md (this file)
├── CLAUDE.md
└── README.md
```

**`my_data/` is gitignored.** Template files, config, and SKILL.md are versioned.

---

## Commands

The Insider provides 5 commands.

---

### `/init` — First-Run Wizard (Entry Point)

**What it does:** Single command to get started — configures Business DNA and Content Map through a conversation. Shows the user that the system now knows their context.

**When to call:** **First thing.** Clone the repo → open in AI Sreda → call `/init`. One time only (until reconfiguration is needed).

**Process:**

#### Step 1: Detect state

```
If business/dna.yaml exists:
  → "Контекст уже настроен. Загружаю текущую конфигурацию:"
  → Show context summary (see Step 2 format)
  → "Данные актуальны? Если нет — скажи, что правим."
  → If user confirms → "Отлично, всё готово. Вызови /extract для интервью."
  → If user wants changes → update and save.

If business/dna.yaml does NOT exist:
  → "Похоже, мы здесь впервые. Давай настроим контекст."
  → Proceed to conversational setup (below)
```

#### Step 2: Show context summary (after config exists)

Show this to the user so they SEE what is loaded:

```
╔══════════════════════════════════════════════════════╗
║  The Insider — Config Loaded                         ║
╠══════════════════════════════════════════════════════╣
║  Компания:  {name} — {description}                  ║
║  Домены:    {domains list}                          ║
║  Продукты:  {products list}                         ║
║  Приоритеты:{strategic priorities list}             ║
║  Аудитории: {audiences list}                        ║
║  Форматы:   {formats list}                          ║
╚══════════════════════════════════════════════════════╝
```

Then confirm: "Это актуально? Если нет — скажи, что поправить. Если всё ок — вызывай /extract."

#### Step 3: Conversational setup (first time)

Collect through dialog (NOT a form — conversational):

```
1. Компания:
   → "Какая компания? Название, чем занимается (1-2 предложения)"

2. Домены (3-7):
   → "В каких тематиках работаете? Перечисли 3-7 направлений."
   → For each, collect keywords: "Какие слова-маркеры? По чему поймём, что история про этот домен?"

3. Продукты / Инициативы (2-5):
   → "Какие ключевые продукты или инициативы? Что важно для внешней коммуникации?"
   → For each: название, keywords, value prop (1 фраза)

4. Стратегические приоритеты (3-5):
   → "Какие 3-5 стратегических приоритетов? Это фильтр: 'эта история работает на стратегию или нет?'"

5. Аудитории (минимум 1, обычно 2-3):
   → "Кто ваши внешние аудитории? (например: госсектор, бизнес, граждане)"
   → For each: название, сегменты, concerns (что их волнует), правила fit (когда история интересна этой аудитории)

6. Форматы (минимум 1, обычно 2-3):
   → "В каких форматах выходите? (Telegram, доклады, кейсы...)"
   → For each: структура, best_for правила
```

Write to `business/dna.yaml` and `business/content_map.yaml`.

#### Step 4: Show loaded context (first time too)

After writing configs, show the context summary (Step 2 format) with:
```
"Готово. Контекст записан. Теперь я знаю о вас вот что:
  [summary]
  Вызови /extract, чтобы провести первое интервью."
```

---

### `/setup` — Reconfigure Business DNA

**What it does:** Same as `/init` but skips the "first run" introduction. Loads current config → shows summary → asks what to change. Use when org context evolves.

---

### `/extract` — Conduct STARRI Interview

**What it does:** Conducts a structured dialog with an expert, extracts a STARRI story, and creates `stories/my_data/{id}.md`.

**Usage:** `/extract`

**Process:**

#### Step 0: Load and show context (Context Briefing)

**IMPORTANT: Before asking any questions, show the user that the system has context.**

```
1. Verify business/dna.yaml and business/content_map.yaml exist.
   If not: "Контекст не настроен. Сначала вызови /init."
   Stop.

2. Load Business DNA + Content Map + Interview Protocol.

3. Show context briefing to user:

   ╔═══════════════════════════════════════════════╗
   ║  The Insider — Context Loaded                 ║
   ╠═══════════════════════════════════════════════╣
   ║  Компания:    {name}                          ║
   ║  Домены:      {domain count}                  ║
   ║  Продукты:    {product count}                 ║
   ║  Приоритеты:  {priority count}                ║
   ║  Аудитории:   {audience list}                 ║
   ║  Форматы:     {format list}                   ║
   ╚═══════════════════════════════════════════════╝

4. "Контекст загружен. Далее я проведу интервью и на основе этих данных
   смапплю историю на аудитории и форматы. Начнём?"
   → User confirms → proceed
   → User says "контекст устарел" → "Давай обновим. Что изменилось?
     (можно вызвать /setup, если изменений много)"
```

#### Step 1: Identify or create expert profile
```
→ "Это новый эксперт или мы уже знакомы?"

If new:
  → Collect: имя, роль, отдел, домен, текущий фокус
  → Create expert profile: experts/profiles/{id}.yaml

If known:
  → Load existing profile
  → Show: "Последний раз работали {date}. Сейчас фокус изменился?"
```

#### Step 2: Conduct STARRI interview (follow protocol.md)

Four phases:

1. **Warm-up** (2-3 questions) — build rapport, find story leads
2. **Story selection** (1 question) — suggest candidate, let expert choose
3. **STARRI extraction** (5-8 questions) — dig into each section
4. **Close** — summarize, ask if there's more

**Rules during extraction:**
- Never read questions from a script. React to answers.
- Always ask for personal contribution ("а что ты лично сделал?")
- Always ask for BEFORE numbers ("было N → стало M?")
- Never generate Insight — extract it from the expert
- All STARRI fields must be covered before finishing

#### Step 3: Write story file

Write to `stories/my_data/{expert-id}-{topic}.md` using the story template.

Set `status: draft`.

#### Step 4: Return summary

Show user:
- Story title
- Key metrics
- Notable insight (if any)
- "Что дальше? Вызови /map, чтобы смапить на контент"

---

### `/map` — Map Story to Audience & Format

**What it does:** Analyzes a story against Business DNA and Content Map, proposes (audience x format x angle) options, and records the choice.

**Usage:** `/map {story_id}` or `/map` (to pick from recent stories)

**Process:**

#### Step 1: Load story

Read story from `stories/my_data/{story_id}.md`. Parse all STARRI fields.

#### Step 2: Score audience fit

For each audience in `content_map.audiences`:

```
score = 0
matches = []

for each rule in audience.story_fit_rules:
    if story attributes match condition:
        score += rule.weight
        matches.append(rule.note)

confidence = score / max_possible_score
```

Sort audiences by score. Take top 2 with confidence > 0.3.

#### Step 3: Score format fit

For each format in `content_map.formats`:

```
if audience.id in format.best_for.audiences:
    base_score = 0.6
    for each attr in format.best_for.story_attributes:
        if story has this attribute:
            base_score += 0.1
    score = min(base_score, 1.0)
else:
    score = 0.2  # still possible, just not ideal
```

Sort formats by score. Take top 2-3 for each audience.

#### Step 4: Select angle

Based on story attributes and (audience, format) pair:

- `result`: if metrics delta > 2x → result angle for b2g/b2b
- `insight`: if insight is surprising → insight angle for b2c/b2b
- `problem`: if problem is relatable → problem angle for b2g/b2c
- `technical`: if strong technical detail → technical for tech audience

#### Step 5: Present to user

```
→ "Для этой истории вижу такие варианты:

   ⭐ [AUDIENCE] → [FORMAT] (angle: [ANGLE])
      Почему: [1-2 sentences of reasoning]

   [AUDIENCE] → [FORMAT] (angle: [ANGLE])
      Почему: [1-2 sentences of reasoning]

   Какой берём? Можем сделать несколько."
```

**This is a decision gate.** Wait for user confirmation before proceeding.

#### Step 6: Record mapping

Update story: `status: mapped`. Optionally record the mapping choice in the story file.

---

### `/generate` — Generate Content Artifact

**What it does:** Generates a content artifact (post/proposal/case study) based on a confirmed mapping.

**Usage:** `/generate {story_id} --audience {id} --format {id} --angle {id}`

Or in dialog: `/generate` → pick story → pick mapping → confirm.

**Process:**

#### Step 1: Load story + mapping

Read story file. Get confirmed audience, format, angle.

#### Step 2: Load audience context

From `content_map.audiences[id]`:
- language_guide
- framing_defaults
- anti_patterns

#### Step 3: Load format template

From `artifacts/templates/{format_id}.md` or `references/{format_id}.md`.

#### Step 4: Generate draft

Apply:
- **Audience framing:** tone, language, proof type from audience config
- **Angle positioning:** structure from `content_map.angles[id]`
- **Format structure:** required sections from format template

**Rules:**
- ALL facts must come from the story. Never add external claims.
- Insight section: leave blank or mark as "не получен" if expert did not provide it.
- Metrics: use ONLY numbers from the story.
- At the end: add `Generated from story: {story_id}` line.

#### Step 5: Review with user

```
→ "Черновик готов:
   [preview — first 200 chars или полный текст]

   Что правим? Если всё ок — сохраняю."
```

#### Step 6: Save

- Write to `artifacts/my_data/{expert-id}-{topic}-{format}.md`
- Update story status: `generated`

---

### `/publish-note` (Optional)

**What it does:** Creates an Insight Card and saves it to the vault/notes system.

**Usage:** `/publish-note {story_id}`

Generates a short note with:
- Expert name and date
- Story title
- Key insight (1-2 sentences)
- Link to story ID and artifact IDs

---

## Mapping Engine (Full Algorithm)

This is the core logic. Follow it step by step.

```
INPUT: STARRI Story

STEP 1 — Extract attributes from story:
  • domains_matched: match story domain keywords against business/domains
  • stakeholder_types: classify stakeholders as 'government' / 'business' / 'public'
  • metric_types: classify metrics as 'time' / 'money' / 'scale' / 'quality'
  • has_insight: true if 'I' section has content from expert
  • narrative_completeness: full (all STARRI filled) / partial / fragment

STEP 2 — Score audience fit:
  FOR each audience in content_map.audiences:
    score = 0
    FOR each rule in audience.story_fit_rules:
      evaluate condition against story attributes
      if match: score += rule.weight
    confidence = score / max_possible
  RETURN audiences sorted by confidence

STEP 3 — Score format for each top audience:
  FOR each format in content_map.formats:
    base = format.best_for.audiences includes audience ? 0.6 : 0.2
    FOR each attr in format.best_for.story_attributes:
      if story matches: base += 0.1
    score = min(base, 1.0)
  RETURN top 2-3 formats

STEP 4 — Select angle:
  • result_angle: metrics_delta > 2x → "Было-стало"
  • insight_angle: has_insight + surprising → "Вот это поворот"
  • problem_angle: relatable problem → "Боль"
  • technical_angle: strong technical detail → "Как это работает"

STEP 5 — Brief:
  FOR each (audience, format, angle) combination:
    Create brief with framing instructions from content_map

STEP 6 — Human decision gate:
  Present options. Let user choose.

STEP 7 — Generate:
  Use format template + audience framing + angle structure + story data
  → content artifact
```

## Quality Checks

### After `/extract`

- [ ] All STARRI fields filled
- [ ] At least 1 metric pair (before/after)
- [ ] Personal contribution identified
- [ ] Insight section — even if "не было ничего неожиданного"
- [ ] No fabricated data
- [ ] Expert profile exists or created

### After `/map`

- [ ] At least 1 audience-confidence > 0.5
- [ ] At least 1 format-confirmed by user
- [ ] Angle fits story attributes

### After `/generate`

- [ ] All facts traceable to story (no invented data)
- [ ] Audience framing applied (tone, language, proof)
- [ ] Format structure respected
- [ ] Insight NOT fabricated (left empty if not provided)
- [ ] Max words respected per format constraints

## References

Templates and configs live in `references/` and `config/`:

| File | Purpose |
|------|---------|
| `references/story.md` | STARRI story template |
| `references/expert.yaml` | Expert profile template |
| `references/telegram_post.md` | Telegram post template |
| `references/talk_proposal.md` | Talk proposal template |
| `references/case_study.md` | Case study template |
| `references/dna.yaml` | Business DNA example (GEMS) |
| `references/content_map.yaml` | Content Map example |
| `config/protocol.md` | Interview protocol for agents |