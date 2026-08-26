"""Handlers for Инсайдер Telegram bot."""

import json
import csv
import io
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import db
from bot.ai import client as ai


# ── Helpers ────────────────────────────────────────────

async def _reply(
    update: Update,
    text: str,
    parse_mode: str | None = None,
    reply_markup=None,
) -> None:
    """Send a reply and log it to conversation_log."""
    user_id = update.effective_user.id
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
    # Log the bot's response
    session = await db.get_session_state(user_id)
    command = session["current_command"] if session else None
    await db.log_conversation(user_id, "bot", text, command)


async def _edit_and_log(query, text: str) -> None:
    """Edit a callback query message and log it."""
    await query.edit_message_text(text)
    user_id = query.from_user.id
    session = await db.get_session_state(user_id)
    command = session["current_command"] if session else None
    await db.log_conversation(user_id, "bot", text, command)

def _format_dna_summary(dna: dict) -> str:
    """Format business DNA as a nice summary box."""
    lines = []
    lines.append("╔═══════════════════════════════════════════════╗")
    lines.append("║  Инсайдер — Config Loaded                ║")
    lines.append("╠═══════════════════════════════════════════════╣")
    lines.append(f"║  Компания:  {dna.get('name', '—')}                ║")
    domains = dna.get("domains", [])
    products = dna.get("products", [])
    priorities = dna.get("strategic_priorities", [])
    lines.append(f"║  Домены:    {len(domains)} шт.                        ║")
    lines.append(f"║  Продукты:  {len(products)} шт.                       ║")
    lines.append(f"║  Приоритеты:{len(priorities)} шт.                      ║")
    lines.append("╚═══════════════════════════════════════════════╝")
    return "\n".join(lines)


# ── /start ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with overview of available commands."""
    user = update.effective_user
    await db.upsert_user(
        telegram_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    # Log start command
    await db.log_conversation(user.id, "user", "/start", "start")

    text = (
        f"Привет, {user.first_name}!\n\n"
        "Я — Инсайдер. Диалоговый агент для вытягивания экспертизы "
        "и упаковки в контент.\n\n"
        "Доступные команды:\n\n"
        "/init — Настроить контекст компании (Business DNA)\n"
        "/extract — Провести STARRI-интервью\n"
        "/map — Смапить историю на аудиторию и формат\n"
        "/generate — Сгенерировать черновик контента\n"
        "/setup — Перенастроить контекст\n"
        "/cancel — Отменить текущее действие\n\n"
        "С чего начнём? Рекомендую /init — это первый шаг."
    )
    await _reply(update, text)


# ── /cancel ─────────────────────────────────────────────

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel current operation."""
    user_id = update.effective_user.id
    # Log the cancel command
    await db.log_conversation(user_id, "user", "/cancel", "cancel")
    await db.clear_session_state(user_id)
    await _reply(update, "Текущее действие отменено. Возвращаюсь в исходное состояние.")


# ── /init — Business DNA setup ──────────────────────────

async def cmd_init(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start or reconfigure business DNA."""
    user_id = update.effective_user.id
    await db.log_conversation(user_id, "user", "/init", "init")
    user = await db.get_user(user_id)

    if user and user.get("business_dna"):
        # Already configured — show summary
        dna = user["business_dna"]
        summary = _format_dna_summary(dna)
        await _reply(
            update,
            f"Контекст уже настроен. Загружаю текущую конфигурацию:\n\n"
            f"```\n{summary}\n```\n"
            "Данные актуальны? Если нет — напиши /setup, чтобы обновить.\n"
            "Если всё ок — вызывай /extract для интервью.",
            parse_mode="Markdown",
        )
        return

    # Start init wizard
    await db.set_session_state(user_id, "init_company", context={"init_step": 0, "answers": {}})
    await _reply(
        update,
        "Похоже, мы здесь впервые. Давай настроим контекст.\n\n"
        "Шаг 1/6: **Компания**\n"
        "Какая компания? Название и чем занимается (1-2 предложения).\n\n"
        "(Отправь /cancel в любой момент, чтобы прервать настройку.)",
        parse_mode="Markdown",
    )


async def cmd_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reconfigure DNA — alias for /init but always starts fresh."""
    user_id = update.effective_user.id
    await db.log_conversation(user_id, "user", "/setup", "setup")
    await db.set_session_state(user_id, "init_company", context={"init_step": 0, "answers": {}})
    await _reply(
        update,
        "Давай обновим контекст.\n\n"
        "Шаг 1/6: **Компания**\n"
        "Какая компания? Название и чем занимается (1-2 предложения).\n\n"
        "(Отправь /cancel в любой момент, чтобы прервать настройку.)",
        parse_mode="Markdown",
    )


async def handle_init_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle each step of the init wizard."""
    user_id = update.effective_user.id
    session = await db.get_session_state(user_id)
    if not session or not session["current_command"].startswith("init_"):
        return False

    text = update.message.text.strip()
    ctx = session.get("context") or {}
    answers = ctx.get("answers", {})
    step = ctx.get("init_step", 0)

    # Map step numbers to keys
    step_keys = ["company", "domains", "products", "priorities", "audiences", "formats"]
    step_questions = [
        "Шаг 1/6: **Компания**\nКакая компания? Название и чем занимается (1-2 предложения).",
        "Шаг 2/6: **Домены**\nВ каких тематиках работаете? Перечисли 3-7 направлений. Для каждого — ключевые слова-маркеры.",
        "Шаг 3/6: **Продукты**\nКакие ключевые продукты или инициативы? 2-5 штук. Для каждого: название, ключевые слова, ценность одной фразой.",
        "Шаг 4/6: **Приоритеты**\nКакие 3-5 стратегических приоритетов? Это фильтр: 'эта история работает на стратегию или нет?'",
        "Шаг 5/6: **Аудитории**\nКто ваши внешние аудитории? Например: госсектор, бизнес, граждане. Для каждой — сегменты, что их волнует.",
        "Шаг 6/6: **Форматы**\nВ каких форматах выходите? Telegram, доклады, кейсы... Для каждого — структура и когда лучше использовать.",
    ]

    if step < len(step_keys):
        answers[step_keys[step]] = text

    next_step = step + 1

    if next_step >= len(step_keys):
        # Done — save DNA
        dna = _build_dna_from_answers(answers)
        await db.update_business_dna(user_id, dna)
        await db.clear_session_state(user_id)

        summary = _format_dna_summary(dna)
        await _reply(
            update,
            f"Готово! Контекст записан. Теперь я знаю о вас вот что:\n\n"
            f"```\n{summary}\n```\n\n"
            "Вызови /extract, чтобы провести первое интервью.",
            parse_mode="Markdown",
        )
        return True

    # Next question
    await db.set_session_state(
        user_id,
        f"init_{step_keys[next_step]}",
        context={"init_step": next_step, "answers": answers},
    )
    await _reply(
        update,
        f"{step_questions[next_step]}",
        parse_mode="Markdown",
    )
    return True


def _build_dna_from_answers(answers: dict) -> dict:
    """Build a structured DNA dict from free-form answers."""
    dna = {
        "name": answers.get("company", "").split("\n")[0][:50],
        "description": answers.get("company", ""),
        "domains": [{"id": "domain-1", "name": d.strip(), "keywords": []}
                     for d in answers.get("domains", "").split("\n") if d.strip()],
        "products": [{"id": f"prod-{i}", "name": p.strip(), "keywords": [], "value_prop": ""}
                      for i, p in enumerate(answers.get("products", "").split("\n")) if p.strip()],
        "strategic_priorities": [p.strip() for p in answers.get("priorities", "").split("\n") if p.strip()],
    }
    return dna


# ── /extract — STARRI Interview ─────────────────────────

async def cmd_extract(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start STARRI interview."""
    user_id = update.effective_user.id
    await db.log_conversation(user_id, "user", "/extract", "extract")
    user = await db.get_user(user_id)

    # Check if DNA is configured
    if not user or not user.get("business_dna"):
        await _reply(
            update,
            "Контекст не настроен. Сначала вызови /init."
        )
        return

    # Check for existing interviews to see if expert is new or known
    interviews = await db.get_user_interviews(user_id, limit=1)

    # Create new interview
    interview = await db.create_interview(user_id)
    interview_id = interview["id"]

    dna = user["business_dna"]
    summary = _format_dna_summary(dna)

    await _reply(
        update,
        f"Контекст загружен.\n\n"
        f"```\n{summary}\n```\n\n"
        f"Далее я проведу STARRI-интервью. Начнём?",
        parse_mode="Markdown",
    )

    # Start with warm-up phase
    await db.set_session_state(
        user_id,
        "extract_warmup",
        context={
            "interview_id": str(interview_id),
            "story": {},
            "chat_history": [],
        },
    )

    # Generate warm-up question
    response = await ai.chat(
        messages=[
            {"role": "user", "content": "Начни интервью. Шаг 1: разогрев. Задай 1-2 вопроса, чтобы познакомиться и найти кандидатные истории. Представься коротко."}
        ],
        system_prompt=ai.SYSTEM_PROMPT_BASE + f"\n\nКонтекст компании: {dna.get('name', '—')}",
        temperature=0.7,
    )
    await _reply(update, response)

    # Save chat history
    session = await db.get_session_state(user_id)
    if session:
        ctx = session.get("context") or {}
        ctx["chat_history"] = ctx.get("chat_history", []) + [
            {"role": "assistant", "content": response}
        ]
        await db.set_session_state(user_id, "extract_warmup", str(interview_id), ctx)


async def handle_extract_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages during the STARRI interview."""
    user_id = update.effective_user.id
    session = await db.get_session_state(user_id)
    if not session:
        return False

    cmd = session["current_command"]
    if not cmd.startswith("extract_"):
        return False

    text = update.message.text.strip()
    ctx = session.get("context") or {}
    story = ctx.get("story", {})
    chat_history = ctx.get("chat_history", [])
    interview_id = ctx.get("interview_id")

    # Add user message to history
    chat_history.append({"role": "user", "content": text})

    # Determine current step
    current_step = cmd.replace("extract_", "")

    # Map step to STARRI field
    step_to_starri = {
        "warmup": None,
        "situation": "situation",
        "task": "task",
        "action": "action",
        "result": "result",
        "relevance": "relevance",
        "insight": "insight",
    }

    if current_step in step_to_starri and step_to_starri[current_step]:
        story[step_to_starri[current_step]] = text

    # Determine next step
    step_order = ["warmup", "situation", "task", "action", "result", "relevance", "insight"]
    current_idx = step_order.index(current_step) if current_step in step_order else -1

    if current_idx >= len(step_order) - 1:
        # Interview complete!
        await db.update_story(interview_id, story, chat_history)
        await db.clear_session_state(user_id)

        # Summary
        story_title = story.get("situation", "—")[:80]
        await _reply(
            update,
            "Интервью завершено! Вот что собрано:\n\n"
            f"**История:** {story_title}\n\n"
            "Что дальше? Вызови /map, чтобы смапить историю на контент.",
            parse_mode="Markdown",
        )

        # Ask AI for a closing message
        response = await ai.chat(
            messages=chat_history[-2:],
            system_prompt="Подведи итог интервью. Скажи, что история записана. Предложи вызвать /map для маппинга.",
            temperature=0.5,
        )
        await _reply(update, response)
        return True

    # Move to next step
    next_step = step_order[current_idx + 1]
    next_step_label = ai.STARRI_STEP_LABELS.get(next_step, next_step)

    # Build system prompt for next step
    user_ctx = await db.get_user(user_id)
    dna = user_ctx.get("business_dna") if user_ctx else None

    system_prompt, _ = ai.build_interview_prompt(next_step, story, dna, [])
    system_prompt += "\n\nПродолжай интервью. Задай 1-2 вопроса по текущему этапу."

    # Generate AI response
    response = await ai.chat(
        messages=chat_history[-6:] if len(chat_history) > 6 else chat_history,
        system_prompt=system_prompt,
        temperature=0.7,
    )
    chat_history.append({"role": "assistant", "content": response})

    await db.set_session_state(
        user_id,
        f"extract_{next_step}",
        interview_id,
        {"story": story, "chat_history": chat_history, "interview_id": interview_id},
    )

    await _reply(update, response)
    return True


# ── /map — Mapping ──────────────────────────────────────

async def cmd_map(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Map story to audience and format."""
    user_id = update.effective_user.id
    await db.log_conversation(user_id, "user", "/map", "map")
    interviews = await db.get_user_interviews(user_id, limit=5)

    # Filter to interviews with stories
    mapped = [i for i in interviews if i.get("story") and i["status"] == "draft"]

    if not mapped:
        await _reply(
            update,
            "Нет историй для маппинга. Сначала проведи интервью — /extract."
        )
        return

    if len(mapped) == 1:
        # Auto-select the only draft
        interview = mapped[0]
        story = interview["story"]
        user_ctx = await db.get_user(user_id)
        dna = user_ctx.get("business_dna") if user_ctx else None

        await _reply(update, "Анализирую историю и подбираю варианты...")

        options = await ai.generate_mapping_options(story, dna)

        # Save mapping context
        await db.set_session_state(
            user_id,
            "map_review",
            str(interview["id"]),
            {"story": story, "options": options},
        )

        await _reply(
            update,
            f"Для этой истории вижу такие варианты:\n\n{options}\n\n"
            "Какой берём? Напиши номер варианта (1, 2...) или опиши словами.\n"
            "Если хочешь другой вариант — просто скажи."
        )
    else:
        # Multiple drafts — let user pick
        keyboard = []
        for i, inv in enumerate(mapped[:5]):
            story_title = (inv["story"].get("situation", "") or "")[:50]
            btn_text = f"{i+1}. {story_title}" if story_title else f"Интервью {i+1}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"map_select_{inv['id']}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await _reply(
            update,
            "Выбери историю для маппинга:",
            reply_markup=reply_markup,
        )


async def handle_map_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback from map selection."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("map_select_"):
        return

    interview_id = data.replace("map_select_", "")
    interview = await db.get_interview(interview_id)

    if not interview or not interview.get("story"):
        await _edit_and_log(query, "История не найдена.")
        return

    story = interview["story"]
    user = await db.get_user(update.effective_user.id)
    dna = user.get("business_dna") if user else None

    await _edit_and_log(query, "Анализирую историю и подбираю варианты...")

    options = await ai.generate_mapping_options(story, dna)

    await db.set_session_state(
        update.effective_user.id,
        "map_review",
        interview_id,
        {"story": story, "options": options},
    )

    await _reply(
        update,
        f"Для этой истории вижу такие варианты:\n\n{options}\n\n"
        "Какой берём? Напиши номер варианта (1, 2...) или опиши словами."
    )


async def handle_map_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's mapping choice."""
    user_id = update.effective_user.id
    session = await db.get_session_state(user_id)
    if not session or session["current_command"] != "map_review":
        return False

    text = update.message.text.strip()
    ctx = session.get("context") or {}
    interview_id = session.get("interview_id")

    # Simple confirmation — just record the mapping
    await db.update_interview_status(interview_id, "mapped")

    # Save mapping choice in context
    ctx["user_choice"] = text
    ctx["mapping_confirmed"] = True
    await db.set_session_state(user_id, "map_confirmed", interview_id, ctx)

    await _reply(
        update,
        f"Принято! Маппинг подтверждён.\n\n"
        f"Теперь вызови /generate, чтобы сгенерировать черновик контента."
    )
    return True


# ── /generate ───────────────────────────────────────────

async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate content from mapped story."""
    user_id = update.effective_user.id
    await db.log_conversation(user_id, "user", "/generate", "generate")
    interviews = await db.get_user_interviews(user_id, limit=5)

    mapped = [i for i in interviews if i["status"] == "mapped"]

    if not mapped:
        await _reply(
            update,
            "Нет смапленных историй. Сначала проведи интервью (/extract) и смапь (/map)."
        )
        return

    if len(mapped) == 1:
        interview = mapped[0]
        story = interview["story"]
        user_ctx = await db.get_user(user_id)
        dna = user_ctx.get("business_dna") if user_ctx else None

        await _reply(
            update,
            "Какой формат и угол?\n\n"
            "Напиши, например:\n"
            "— Telegram-пост, результат\n"
            "— Заявка на доклад, проблема\n"
            "— Кейс, инсайт\n"
            "— технический разбор\n\n"
            "Или просто опиши, что нужно."
        )

        await db.set_session_state(
            user_id,
            "generate_confirm",
            str(interview["id"]),
            {"story": story},
        )
    else:
        keyboard = []
        for i, inv in enumerate(mapped[:5]):
            story_title = (inv["story"].get("situation", "") or "")[:50]
            btn_text = f"{i+1}. {story_title}" if story_title else f"История {i+1}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"gen_select_{inv['id']}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await _reply(
            update,
            "Выбери историю для генерации:",
            reply_markup=reply_markup,
        )


async def handle_generate_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback from generate selection."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if not data.startswith("gen_select_"):
        return

    interview_id = data.replace("gen_select_", "")
    interview = await db.get_interview(interview_id)

    if not interview or not interview.get("story"):
        await _edit_and_log(query, "История не найдена.")
        return

    story = interview["story"]

    await db.set_session_state(
        update.effective_user.id,
        "generate_confirm",
        interview_id,
        {"story": story},
    )

    await _edit_and_log(query,
        "Какой формат и угол?\n\n"
        "Напиши, например:\n"
        "— Telegram-пост, результат\n"
        "— Заявка на доклад, проблема\n"
        "— Кейс, инсайт\n"
        "— технический разбор"
    )


async def handle_generate_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user's format/angle choice and generate."""
    user_id = update.effective_user.id
    session = await db.get_session_state(user_id)
    if not session or session["current_command"] != "generate_confirm":
        return False

    text = update.message.text.strip().lower()
    ctx = session.get("context") or {}
    interview_id = session.get("interview_id")
    story = ctx.get("story", {})

    # Parse format and angle from user's message
    format_map = {
        "telegram": "telegram_post",
        "пост": "telegram_post",
        "telegram-пост": "telegram_post",
        "доклад": "talk_proposal",
        "заявка": "talk_proposal",
        "заявка на доклад": "talk_proposal",
        "кейс": "case_study",
        "case": "case_study",
        "case study": "case_study",
    }
    angle_map = {
        "результат": "result",
        "было-стало": "result",
        "проблема": "problem",
        "боль": "problem",
        "инсайт": "insight",
        "вот это поворот": "insight",
        "технический": "technical",
        "как это работает": "technical",
    }

    format_id = "telegram_post"
    angle_id = "result"

    for key, val in format_map.items():
        if key in text:
            format_id = val
            break

    for key, val in angle_map.items():
        if key in text:
            angle_id = val
            break

    await _reply(update, "Генерирую черновик...")

    user_ctx = await db.get_user(user_id)
    dna = user_ctx.get("business_dna") if user_ctx else None

    content = await ai.generate_artifact(story, "b2b", format_id, angle_id, dna)

    # Save artifact
    await db.create_artifact(
        interview_id=interview_id,
        user_id=user_id,
        audience_id="b2b",
        format_id=format_id,
        angle_id=angle_id,
        content=content,
    )

    await db.update_interview_status(interview_id, "generated")
    await db.clear_session_state(user_id)

    await _reply(
        update,
        f"Черновик готов:\n\n{content}\n\n"
        "Что правим? Если всё ок — история готова.\n"
        "Хочешь сделать ещё один вариант — вызови /generate снова."
    )
    return True


# ── /admin ──────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin panel — view users and data, or download logs."""
    user_id = update.effective_user.id
    user = await db.get_user(user_id)

    if not user or not user.get("is_admin"):
        await _reply(update, "Доступ запрещён.")
        return

    # Log admin command
    cmd_text = update.message.text.strip()
    await db.log_conversation(user_id, "user", cmd_text, "admin")

    # Handle subcommands
    args = context.args
    if args and args[0] == "download":
        return await cmd_admin_download(update, context)

    # Get conversation stats
    stats = await db.get_conversation_stats()

    text = (
        "<b>Панель администратора</b>\n\n"
        "<b>Статистика переписки:</b>\n"
        f"Всего сообщений: {stats['total_messages']}\n"
        f"Всего пользователей: {stats['total_users']}\n"
        f"За последние 24ч: {stats['last_24h']}\n\n"
        f"<b>Активность пользователей:</b>\n"
    )
    for u in stats.get("users", []):
        name = html.escape(u.get("first_name") or u.get("username") or str(u["telegram_id"]))
        text += f"• {name} — {u['msg_count']} сообщ., последнее: {u['last_msg'].strftime('%d.%m %H:%M') if u.get('last_msg') else '—'}\n"

    text += (
        "\n<b>Команды:</b>\n"
        "/admin — Показать эту панель\n"
        "/admin download — Скачать все логи переписки (CSV)\n"
        "/admin download &lt;user_id&gt; — Скачать логи конкретного пользователя (CSV)"
    )

    await _reply(update, text, parse_mode="HTML")


async def cmd_admin_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Download conversation logs as CSV."""
    user_id = update.effective_user.id
    user = await db.get_user(user_id)

    if not user or not user.get("is_admin"):
        await _reply(update, "Доступ запрещён.")
        return

    # Parse args: /admin download [user_id]
    # args[0] is "download" when called from cmd_admin, so skip it
    args = context.args
    if args and args[0] == "download":
        args = args[1:]
    target_user_id = None
    if args:
        try:
            target_user_id = int(args[0])
        except ValueError:
            await _reply(update, "Неверный ID пользователя. Используй: /admin download <user_id>")
            return

    logs = await db.get_conversation_logs(user_id=target_user_id, limit=10000)

    if not logs:
        await _reply(update, "Нет данных для выгрузки.")
        return

    # Build CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "user_id", "role", "text", "command", "created_at"])
    for row in logs:
        writer.writerow([
            row["id"],
            row["user_id"],
            row["role"],
            row["text"],
            row.get("command", ""),
            row["created_at"].strftime("%Y-%m-%d %H:%M:%S") if row.get("created_at") else "",
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")
    # Send as a file
    await update.message.reply_document(
        document=io.BytesIO(csv_bytes),
        filename=f"conversation_log_{target_user_id or 'all'}.csv",
        caption=f"Логи переписки ({'все пользователи' if not target_user_id else f'пользователь {target_user_id}'})",
    )


# ── Message router ──────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route incoming messages based on current session state."""
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    session = await db.get_session_state(user_id)
    if not session:
        return

    cmd = session["current_command"]

    # Log user message
    await db.log_conversation(user_id, "user", update.message.text.strip(), cmd)

    # Route to appropriate handler
    if cmd.startswith("init_"):
        await handle_init_step(update, context)
    elif cmd.startswith("extract_"):
        await handle_extract_message(update, context)
    elif cmd == "map_review":
        await handle_map_review(update, context)
    elif cmd == "generate_confirm":
        await handle_generate_confirm(update, context)