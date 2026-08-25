"""AI client for Инсайдер Service.
Wraps OpenAI-compatible API (polza.ai) with model-agnostic interface.
"""

import os
from openai import AsyncOpenAI
from typing import Optional

_client: Optional[AsyncOpenAI] = None

SYSTEM_PROMPT_BASE = """Ты — The Insider. Диалоговый агент для вытягивания экспертизы и упаковки в контент.

Твоя задача — провести STARRI-интервью с экспертом и записать историю.

## Правила работы
1. Ты партнёр, а не опросник. Реагируй на ответы, не читай вопросы по списку.
2. Facts Only Rule — никогда не выдумывай метрики, результаты или инсайты.
3. Insight (раздел I) должен прийти от эксперта. Ты НЕ генерируешь его сам.
4. Личный вклад критичен — если эксперт говорит "мы", спроси "а что ты лично сделал?".
5. Все поля STARRI должны быть заполнены перед завершением.
6. Не пиши рефлексию — это только за человеком.

## Структура STARRI
- S (Situation) — контекст: проект, сроки, стейкхолдеры, ставки
- T (Task) — задача: цель, метрика успеха, ограничения
- A (Action) — действия: подход, личный вклад, инструменты, команда, сроки
- R (Result) — результат: было N → стало M, бизнес-эффект, масштаб
- R (Relevance) — актуальность: кто должен услышать, почему это важно, крючок
- I (Insight) — инсайт: что удивило, что бы сделал иначе, урок
"""


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ["POLZA_API_KEY"],
            base_url=os.environ.get("POLZA_BASE_URL", "https://api.polza.ai/v1"),
        )
    return _client


def get_model() -> str:
    return os.environ.get("AI_MODEL", "deepseek-v4-flash")


async def chat(
    messages: list[dict],
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Send a chat completion request. Returns the response text."""
    client = get_client()
    model = get_model()

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})

    full_messages.extend(messages)

    response = await client.chat.completions.create(
        model=model,
        messages=full_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


# ── Interview state machine ────────────────────────────

STARRI_STEPS = ["situation", "task", "action", "result", "relevance", "insight"]

STARRI_STEP_LABELS = {
    "situation": "S — Situation (Context)",
    "task": "T — Task (Goal)",
    "action": "A — Action (What We Did)",
    "result": "R — Result (Measurable Outcome)",
    "relevance": "R — Relevance (Audience)",
    "insight": "I — Insight (The Gold)",
}

STARRI_STEP_PROMPTS = {
    "situation": """Ты на этапе S — Situation. Задача: собрать контекст истории.

Что нужно выяснить:
- Название проекта / инициативы
- Сроки (когда началось, когда закончилось)
- Стейкхолдеры (кто вовлечён, команды, внешние стороны)
- Что было на кону — почему это важно

Задай 1-2 вопроса. Реагируй на ответ. Когда контекст ясен — скажи "Понял, [коротко перескажи]" и переходи к следующему шагу.""",

    "task": """Ты на этапе T — Task. Задача: понять, какая конкретно стояла цель.

Что нужно выяснить:
- Какая была задача / цель?
- В чём измерялся успех? (должна быть измеримая метрика, если возможно)
- Были ли ограничения? (бюджет, время, регуляторика)

Задай 1-2 вопроса. Когда задача ясна — подтверди и переходи к следующему шагу.""",

    "action": """Ты на этапе A — Action. Задача: понять, что конкретно делали.

Что нужно выяснить:
- Какой был подход / стратегия?
- Что эксперт лично сделал? (ВАЖНО: спроси "а что ты лично делал?")
- Какие инструменты, технологии использовали?
- Сколько человек в команде, сколько времени заняла активная работа?

Задай 1-2 вопроса. Когда действия ясны — подтверди и переходи к следующему шагу.""",

    "result": """Ты на этапе R — Result. Задача: получить конкретные цифры.

Что нужно выяснить:
- Что изменилось? Было N → стало M? (ОБЯЗАТЕЛЬНО: спроси "а сколько было ДО?")
- Какой бизнес-эффект?
- Масштаб: сколько регионов, пользователей, транзакций?

Задай 1-2 вопроса. ВАЖНО: добейся пары "было → стало". Когда цифры есть — подтверди и переходи.""",

    "relevance": """Ты на этапе R — Relevance. Задача: определить, кому эта история полезна.

Что нужно выяснить:
- Кто должен услышать эту историю? (предложи варианты из контекста компании)
- Почему это важно именно им?
- Как одним предложением зацепить внимание? (narrative hook)

ВАЖНО: не спрашивай "какую аудиторию видишь?" — предложи и спроси "ты согласен?".
Когда ясно — подтверди и переходи.""",

    "insight": """Ты на этапе I — Insight. Задача: вытащить неочевидное.

Что нужно выяснить:
- Что самое удивительное / неочевидное в этой истории?
- Если бы начинал заново — что бы сделал иначе?
- Какой урок вынес?

Если эксперт даёт общий ответ — копни глубже: "То есть главная проблема была не в технологии, а в...?"
Если эксперт не может сформулировать — спроси "А что в процессе больше всего удивило?"

Когда инсайт получен (или эксперт сказал, что не было неожиданного) — заверши интервью.""",
}


def build_interview_prompt(
    step: str,
    story_so_far: dict,
    business_dna: dict | None,
    chat_history: list[dict],
) -> tuple[str, list[dict]]:
    """Build system prompt and messages for the current interview step."""
    # Build context summary
    context_parts = []
    if business_dna:
        context_parts.append(f"Компания: {business_dna.get('name', '—')}")
        domains = business_dna.get('domains', [])
        if domains:
            context_parts.append(f"Домены: {', '.join(d.get('name', '') for d in domains)}")
        products = business_dna.get('products', [])
        if products:
            context_parts.append(f"Продукты: {', '.join(p.get('name', '') for p in products)}")

    context_str = "\n".join(context_parts) if context_parts else "Контекст не настроен"

    system_prompt = f"""Ты — The Insider. Диалоговый агент для вытягивания экспертизы.

## Контекст компании
{context_str}

## Текущий этап интервью: {STARRI_STEP_LABELS.get(step, step)}

{STARRI_STEP_PROMPTS.get(step, "Проведи интервью по STARRI.")}

## Что уже собрано
{_format_story_so_far(story_so_far)}

## Правила
- Никогда не выдумывай факты
- Если эксперт не дал цифру — не пиши её
- Реагируй на ответы, не читай скрипт
- Когда этап завершён, скажи об этом чётко: "[ЭТАП ЗАВЕРШЁН]"
"""

    return system_prompt, chat_history


def _format_story_so_far(story: dict) -> str:
    parts = []
    for key in STARRI_STEPS:
        label = STARRI_STEP_LABELS.get(key, key)
        value = story.get(key, "")
        if value:
            parts.append(f"--- {label} ---\n{value}\n")
    if not parts:
        return "Пока ничего не собрано."
    return "\n".join(parts)


# ── Mapping prompts ────────────────────────────────────

async def generate_mapping_options(
    story: dict,
    business_dna: dict | None,
) -> str:
    """Ask AI to analyze story and propose audience x format x angle options."""
    system_prompt = """Ты — Mapping Engine The Insider. Твоя задача — проанализировать STARRI-историю и предложить варианты упаковки в контент.

Алгоритм:
1. Оцени, какой аудитории (B2G, B2B, B2C) эта история интересна на основе стейкхолдеров, метрик, домена
2. Для каждой аудитории подбери подходящий формат (telegram_post, talk_proposal, case_study) и угол (result, problem, insight, technical)
3. Объясни, почему каждый вариант подходит

Предложи 2-3 варианта. Формат ответа:
⭐ [АУДИТОРИЯ] → [ФОРМАТ] (угол: [УГОЛ])
Почему: [1-2 предложения]"""

    if business_dna:
        audiences = business_dna.get("content_map", {}).get("audiences", [])
        if audiences:
            system_prompt += f"\n\nДоступные аудитории: {', '.join(a.get('name', '') for a in audiences)}"

    story_text = _format_story_so_far(story)
    response = await chat(
        messages=[
            {"role": "user", "content": f"Вот история:\n\n{story_text}\n\nПредложи варианты маппинга."}
        ],
        system_prompt=system_prompt,
        temperature=0.5,
    )
    return response


# ── Generation prompts ─────────────────────────────────

async def generate_artifact(
    story: dict,
    audience_id: str,
    format_id: str,
    angle_id: str,
    business_dna: dict | None,
) -> str:
    """Generate content artifact based on confirmed mapping."""
    format_names = {
        "telegram_post": "Telegram-пост",
        "talk_proposal": "Заявка на доклад",
        "case_study": "Кейс",
    }
    angle_names = {
        "result": "Результат / Было-стало",
        "problem": "Проблема / Боль",
        "insight": "Инсайт / Вот это поворот",
        "technical": "Технический / Как это работает",
    }

    format_word_counts = {
        "telegram_post": "350-400 слов",
        "talk_proposal": "250-300 слов",
        "case_study": "1200-1500 слов",
    }

    system_prompt = f"""Ты — генератор контента The Insider.

Сгенерируй {format_names.get(format_id, format_id)}.

Угол подачи: {angle_names.get(angle_id, angle_id)}
Максимальный объём: {format_word_counts.get(format_id, '400 слов')}

## Правила
1. ВСЕ факты должны быть из истории. Никаких внешних утверждений.
2. Не придумывай метрики — используй ТОЛЬКО те, что в истории.
3. Если инсайт (I) пустой — не пиши раздел с инсайтом.
4. В конце добавь строку: "Generated from story interview"
5. Соблюдай ограничение по объёму."""

    if business_dna:
        vocab = business_dna.get("vocabulary", {})
        if vocab:
            preferred = vocab.get("preferred", [])
            avoid = vocab.get("avoid", [])
            if preferred:
                system_prompt += f"\nПредпочтительные термины: {', '.join(preferred)}"
            if avoid:
                system_prompt += f"\nИзбегай терминов: {', '.join(avoid)}"

    story_text = _format_story_so_far(story)
    response = await chat(
        messages=[
            {"role": "user", "content": f"Сгенерируй контент на основе этой истории:\n\n{story_text}"}
        ],
        system_prompt=system_prompt,
        temperature=0.7,
    )
    return response


# ── Init assistant ─────────────────────────────────────

async def generate_init_questions(step: int, previous_answers: dict) -> str:
    """Generate the next question for the /init conversational wizard."""
    init_steps = [
        "company",
        "domains",
        "products",
        "priorities",
        "audiences",
        "formats",
    ]

    current_step = init_steps[step] if step < len(init_steps) else "done"

    prompts = {
        "company": "Какая компания? Название и чем занимается (1-2 предложения).",
        "domains": "В каких тематиках работаете? Перечисли 3-7 направлений. Для каждого — ключевые слова-маркеры.",
        "products": "Какие ключевые продукты или инициативы? 2-5 штук. Для каждого: название, ключевые слова, ценность одной фразой.",
        "priorities": "Какие 3-5 стратегических приоритетов? Это фильтр: 'эта история работает на стратегию или нет?'",
        "audiences": "Кто ваши внешние аудитории? Например: госсектор, бизнес, граждане. Для каждой — сегменты, что их волнует.",
        "formats": "В каких форматах выходите? Telegram, доклады, кейсы... Для каждого — структура и когда лучше использовать.",
    }

    return prompts.get(current_step, "Всё собрано. Спасибо!")