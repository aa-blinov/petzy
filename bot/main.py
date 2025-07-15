"""Main entry point for the Telegram bot application."""

from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from bot.config import TELEGRAM_BOT_TOKEN
from bot.db import init_db
from bot.handlers import (
    ask_defe_event_datetime,
    ask_defe_stool_type,
    ask_event_datetime,
    ask_export_type,
    ask_type,
    asthma_comment,
    asthma_duration,
    asthma_inhalation,
    asthma_reason,
    defe_comment,
    export_format,
    handle_defe_event_date_input,
    handle_defe_event_time_input,
    handle_event_date_input,
    handle_event_time_input,
    start,
)

MAIN_MENU = 0
ASK_EVENT_DATETIME = 20
HANDLE_EVENT_DATE = 22
HANDLE_EVENT_TIME = 23
ASK_ASTHMA_DURATION = 1
ASK_ASTHMA_REASON = 2
ASK_ASTHMA_INHALATION = 3
SAVE_ASTHMA_COMMENT = 4
ASK_DEFE_EVENT_DATETIME = 21
HANDLE_DEFE_EVENT_DATE = 24
HANDLE_DEFE_EVENT_TIME = 25
ASK_DEFE_STOOL_TYPE = 5
SAVE_DEFE_COMMENT = 6
CHOOSE_EXPORT_TYPE = 7
CHOOSE_EXPORT_FORMAT = 8


def main() -> None:
    """Main function to start the Telegram bot."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_type)],
            ASK_EVENT_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_event_datetime)],
            HANDLE_EVENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_date_input)],
            HANDLE_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_event_time_input)],
            ASK_ASTHMA_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_duration)],
            ASK_ASTHMA_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_reason)],
            ASK_ASTHMA_INHALATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_inhalation)],
            SAVE_ASTHMA_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_comment)],
            ASK_DEFE_EVENT_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_defe_event_datetime)],
            HANDLE_DEFE_EVENT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_defe_event_date_input)],
            HANDLE_DEFE_EVENT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_defe_event_time_input)],
            ASK_DEFE_STOOL_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_defe_stool_type)],
            SAVE_DEFE_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, defe_comment)],
            CHOOSE_EXPORT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_export_type)],
            CHOOSE_EXPORT_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, export_format)],
        },
        fallbacks=[CommandHandler("start", start)],
    )
    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    init_db()
    main()
