# The Insider — Project-Level Instructions

## What This Is

The Insider — диалоговый агент для вытягивания экспертизы и упаковки в контент. Проводит структурированное интервью с экспертом, извлекает STARRI-историю, маппит на аудиторию и формат, генерирует черновик контента (Telegram-пост, заявку на доклад, кейс).

## Directory Structure

```
the-insider/
├── .claude/skills/the-insider/
│   ├── SKILL.md          — The Insider skill (entry point)
│   ├── config/
│   │   └── protocol.md   — Interview protocol instructions
│   └── references/       — Templates referenced by skill
│       ├── story.md
│       ├── telegram_post.md
│       ├── talk_proposal.md
│       └── case_study.md
├── business/
│   ├── dna.yaml          — Business DNA (company identity, domains)
│   └── content_map.yaml  — Audiences, formats, mapping rules
├── experts/
│   └── profiles/         — Expert profiles (my_data/)
├── stories/
│   └── my_data/          — Expertise stories (my_data/)
├── artifacts/
│   └── my_data/          — Generated content artifacts (my_data/)
├── CLAUDE.md
├── README.md
└── .gitignore
```

## Skills

- `the-insider` — The Insider skill with commands: /init, /setup, /extract, /map, /generate

## Rules

1. `my_data/` tracked by .gitignore — не коммитится
2. Templates, SKILL.md, references, config — коммитятся
3. Перед запуском /extract — проверь, что `business/dna.yaml` существует
4. Если dna.yaml нет — предложи вызвать /init