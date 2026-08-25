"""The Insider Service — Telegram Bot Entry Point.

Run: python -m bot.main
"""

import os
import logging
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import db
from bot.handlers import (
    cmd_start,
    cmd_init,
    cmd_setup,
    cmd_extract,
    cmd_map,
    cmd_generate,
    cmd_admin,
    cmd_cancel,
    handle_message,
    handle_map_selection,
    handle_generate_selection,
)

# ── Config ──────────────────────────────────────────────

load_dotenv()
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Startup/Shutdown ───────────────────────────────────

async def post_init(application: Application) -> None:
    """Initialize database pool and apply schema on startup."""
    await db.init_pool()
    await db.run_migrations()
    logger.info("Database pool initialized and migrations applied")
    logger.info(f"Bot started. Admin IDs: {ADMIN_IDS}")


async def post_shutdown(application: Application) -> None:
    """Close database pool on shutdown."""
    await db.close_pool()
    logger.info("Database pool closed")


# ── Error handler ──────────────────────────────────────

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user."""
    error = context.error
    logger.error("Exception while handling an update: %s", error, exc_info=True)

    if update and update.effective_message:
        await update.effective_message.reply_text(
            f"Произошла ошибка: {error}\n\nПопробуйте ещё раз или вызовите /cancel."
        )


# ── Main ────────────────────────────────────────────────

def main() -> None:
    """Build and run the bot."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ── Commands ──
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("init", cmd_init))
    application.add_handler(CommandHandler("setup", cmd_setup))
    application.add_handler(CommandHandler("extract", cmd_extract))
    application.add_handler(CommandHandler("map", cmd_map))
    application.add_handler(CommandHandler("generate", cmd_generate))
    application.add_handler(CommandHandler("admin", cmd_admin))
    application.add_handler(CommandHandler("cancel", cmd_cancel))

    # ── Callbacks (inline keyboards) ──
    application.add_handler(CallbackQueryHandler(handle_map_selection, pattern="^map_select_"))
    application.add_handler(CallbackQueryHandler(handle_generate_selection, pattern="^gen_select_"))

    # ── Messages (stateful) ──
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ── Errors ──
    application.add_error_handler(error_handler)

    # ── Start ──
    logger.info("Starting bot polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()