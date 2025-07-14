import logging
import os
from datetime import datetime
from typing import List, Optional

from db import AsthmaAttack, AsthmaType, Defecation, StoolType, WhitelistUser, init_db
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)

"""Основной модуль Telegram-бота для контроля здоровья кота."""
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# States for ConversationHandler
(
    MAIN_MENU,
    ASK_ASTHMA_DURATION,
    ASK_ASTHMA_REASON,
    ASK_ASTHMA_INHALATION,
    SAVE_ASTHMA_COMMENT,
    ASK_DEFE_STOOL_TYPE,
    SAVE_DEFE_COMMENT,
    CHOOSE_EXPORT_TYPE,
    CHOOSE_EXPORT_FORMAT,
) = range(9)


# Клавиатуры
main_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Приступ астмы")], [KeyboardButton("Дефекация")], [KeyboardButton("Выгрузить данные")]],
    resize_keyboard=True,
)
export_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Выгрузить приступы астмы")], [KeyboardButton("Выгрузить дефекации")], [KeyboardButton("В меню")]],
    resize_keyboard=True,
)
format_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Выгрузить как CSV")],
        [KeyboardButton("Выгрузить как markdown-файл")],
        [KeyboardButton("Выгрузить как сообщение")],
        [KeyboardButton("В меню")],
    ],
    resize_keyboard=True,
)
menu_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("В меню")]],
    resize_keyboard=True,
)
comment_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Пропустить")], [KeyboardButton("В меню")]],
    resize_keyboard=True,
)
stool_type_keyboard = ReplyKeyboardMarkup(
    [[KeyboardButton("Обычный"), KeyboardButton("Твердый"), KeyboardButton("Жидкий")], [KeyboardButton("В меню")]],
    resize_keyboard=True,
)


async def is_whitelisted(user_id: int) -> bool:
    """Проверяет, находится ли пользователь в белом списке (асинхронно)."""
    engine = create_async_engine(
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    async with AsyncSession(engine) as session:
        result = await session.execute(WhitelistUser.__table__.select().where(WhitelistUser.telegram_id == user_id))
        user = result.first()
    await engine.dispose()
    return user is not None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик команды /start. Приветствие и проверка белого списка."""
    user_id: int = update.effective_user.id
    if not await is_whitelisted(user_id):
        await update.message.reply_text("Вы не в белом списке. Обратитесь к администратору.")
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "Привет! Я помогу вам следить за здоровьем Саймона 🐾. Что запишем?", reply_markup=main_keyboard
    )
    return MAIN_MENU


async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора действия пользователем (астма, дефекация, выгрузка)."""
    text: Optional[str] = update.message.text
    if text == "Приступ астмы":
        context.user_data.clear()
        await update.message.reply_text(
            "Какой это был приступ у котика? 😿",
            reply_markup=ReplyKeyboardMarkup(
                [["Короткий", "Длительный"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )
        return ASK_ASTHMA_DURATION
    elif text == "Дефекация":
        context.user_data.clear()
        await update.message.reply_text("Какой был стул у Саймона? 🚽", reply_markup=stool_type_keyboard)
        return ASK_DEFE_STOOL_TYPE
    elif text == "Выгрузить данные":
        await update.message.reply_text("Хотите посмотреть историю записей? 📈", reply_markup=export_keyboard)
        return CHOOSE_EXPORT_TYPE
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите действие с помощью кнопок 🙏.", reply_markup=main_keyboard
        )
        return MAIN_MENU


async def asthma_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора длительности приступа астмы."""
    duration: Optional[str] = update.message.text
    if duration == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU
    if duration not in ["Короткий", "Длительный"]:
        await update.message.reply_text(
            'Пожалуйста, выберите "Короткий" или "Длительный" 😿.',
            reply_markup=ReplyKeyboardMarkup(
                [["Короткий", "Длительный"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )
        return ASK_ASTHMA_DURATION
    context.user_data["duration"] = AsthmaType.short if duration == "Короткий" else AsthmaType.long
    # Кнопки для причины астмы
    reason_keyboard = ReplyKeyboardMarkup(
        [["Пил после сна", "Другое"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Что могло стать причиной? 🧐", reply_markup=reason_keyboard)
    return ASK_ASTHMA_REASON


async def asthma_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка причины приступа астмы (свободный ввод)."""
    reason: Optional[str] = update.message.text
    if reason == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU
    if reason is None or not reason.strip():
        await update.message.reply_text(
            "Опишите причину, пожалуйста. Это важно для здоровья Саймона.", reply_markup=menu_keyboard
        )
        return ASK_ASTHMA_REASON

    context.user_data["reason"] = reason.strip()
    inhalation_keyboard = ReplyKeyboardMarkup([["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Делали ингаляцию? 💨", reply_markup=inhalation_keyboard)
    return ASK_ASTHMA_INHALATION


async def asthma_inhalation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка ответа о проведении ингаляции."""
    inhalation: Optional[str] = update.message.text
    if inhalation == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU
    if inhalation is None:
        inhalation_keyboard = ReplyKeyboardMarkup(
            [["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text('Нужно выбрать "Да" или "Нет" 🙏.', reply_markup=inhalation_keyboard)
        return ASK_ASTHMA_INHALATION
    inhalation_l = inhalation.lower()
    if inhalation_l not in ["да", "нет"]:
        inhalation_keyboard = ReplyKeyboardMarkup(
            [["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text('Нужно выбрать "Да" или "Нет" 🙏.', reply_markup=inhalation_keyboard)
        return ASK_ASTHMA_INHALATION
    context.user_data["inhalation"] = inhalation_l == "да"
    await update.message.reply_text("Хотите добавить комментарий? 📝", reply_markup=comment_keyboard)
    return SAVE_ASTHMA_COMMENT


async def asthma_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение приступа астмы в БД (асинхронно)."""
    comment: Optional[str] = update.message.text
    if comment == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU

    user_id: int = update.effective_user.id
    now: datetime = datetime.now()
    engine = create_async_engine(
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    async with AsyncSession(engine) as session:
        attack = AsthmaAttack(
            user_id=user_id,
            date_time=now,
            duration=context.user_data["duration"],
            reason=context.user_data["reason"],
            inhalation=context.user_data["inhalation"],
            comment=None if comment is None or comment.strip() == "-" or comment == "Пропустить" else comment.strip(),
        )
        session.add(attack)
        await session.commit()
    await engine.dispose()
    await update.message.reply_text("Записал! Надеюсь, Саймону уже лучше. ❤️‍🩹", reply_markup=main_keyboard)
    context.user_data.clear()
    return MAIN_MENU


async def ask_defe_stool_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора вида стула."""
    stool_type_text: Optional[str] = update.message.text
    if stool_type_text == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU

    if stool_type_text not in [s.value for s in StoolType]:
        await update.message.reply_text(
            "Пожалуйста, выберите вид стула с помощью кнопок.", reply_markup=stool_type_keyboard
        )
        return ASK_DEFE_STOOL_TYPE

    context.user_data["stool_type"] = StoolType(stool_type_text)
    await update.message.reply_text("Хотите добавить комментарий? 📝", reply_markup=comment_keyboard)
    return SAVE_DEFE_COMMENT


async def defe_comment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение дефекации в БД (асинхронно)."""
    comment: Optional[str] = update.message.text
    if comment == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU
    user_id: int = update.effective_user.id
    now: datetime = datetime.now()
    engine = create_async_engine(
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    async with AsyncSession(engine) as session:
        defe = Defecation(
            user_id=user_id,
            date_time=now,
            stool_type=context.user_data["stool_type"],
            comment=None if comment is None or comment.strip() == "-" or comment == "Пропустить" else comment.strip(),
        )
        session.add(defe)
        await session.commit()
    await engine.dispose()
    await update.message.reply_text("Отметил! Чистый лоток - залог здоровья! ✨", reply_markup=main_keyboard)
    context.user_data.clear()
    return MAIN_MENU


async def ask_export_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выбор типа данных для экспорта."""
    text: Optional[str] = update.message.text
    if text == "В меню":
        context.user_data.clear()
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return MAIN_MENU

    if text == "Выгрузить приступы астмы":
        context.user_data["export_type"] = "asthma"
        await update.message.reply_text("В каком формате выгрузить данные? 📄", reply_markup=format_keyboard)
        return CHOOSE_EXPORT_FORMAT
    elif text == "Выгрузить дефекации":
        context.user_data["export_type"] = "defecation"
        await update.message.reply_text("В каком формате выгрузить данные? 📄", reply_markup=format_keyboard)
        return CHOOSE_EXPORT_FORMAT
    else:
        await update.message.reply_text("Пожалуйста, выберите, что именно выгрузить. 🙏", reply_markup=export_keyboard)
        return CHOOSE_EXPORT_TYPE


async def export_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора формата выгрузки и сама выгрузка."""
    text: Optional[str] = update.message.text
    export_type = context.user_data.get("export_type")

    if text == "В меню":
        del context.user_data["export_type"]
        await update.message.reply_text("Что именно выгрузить? 📈", reply_markup=export_keyboard)
        return CHOOSE_EXPORT_TYPE

    if not export_type:
        await update.message.reply_text(
            "Ой, что-то пошло не так. Давайте начнем сначала, чтобы ничего не потерять. 🙏", reply_markup=main_keyboard
        )
        context.user_data.clear()
        return MAIN_MENU

    engine = create_async_engine(
        f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )
    async with AsyncSession(engine) as session:
        if export_type == "asthma":
            result = await session.execute(select(AsthmaAttack).order_by(AsthmaAttack.date_time.asc()))
            attacks: List[AsthmaAttack] = result.scalars().all()
            headers = ["Дата", "Время", "Пользователь", "Длительность", "Причина", "Ингаляция", "Комментарий"]
            if text == "Выгрузить как CSV":
                import csv

                csv_path = "asthma_attacks_export.csv"
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for a in attacks:
                        writer.writerow(
                            [
                                a.date_time.strftime("%Y-%m-%d"),
                                a.date_time.strftime("%H:%M"),
                                a.user_id,
                                "Длительный" if a.duration == AsthmaType.long else "Короткий",
                                a.reason,
                                "Да" if a.inhalation else "Нет",
                                a.comment or "",
                            ]
                        )
                with open(csv_path, "rb") as f:
                    await update.message.reply_document(f, filename="asthma_attacks_export.csv")
            elif text == "Выгрузить как сообщение":
                msg = []
                for a in attacks:
                    msg.append(
                        f"Дата: {a.date_time.strftime('%Y-%m-%d')}\n"
                        f"Время: {a.date_time.strftime('%H:%M')}\n"
                        f"Пользователь: {a.user_id}\n"
                        f"Длительность: {'Длительный' if a.duration == AsthmaType.long else 'Короткий'}\n"
                        f"Причина: {a.reason}\n"
                        f"Ингаляция: {'Да' if a.inhalation else 'Нет'}\n"
                        f"Комментарий: {a.comment or '-'}\n"
                        f"---"
                    )
                text_out = "\n".join(msg) if msg else "Нет данных."
                await update.message.reply_text(text_out)
            elif text == "Выгрузить как markdown-файл":
                md_path = "asthma_attacks_export.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("| " + " | ".join(headers) + " |\n")
                    f.write("|" + "---|" * len(headers) + "\n")
                    for a in attacks:
                        f.write(
                            f"| {a.date_time.strftime('%Y-%m-%d')} | {a.date_time.strftime('%H:%M')} | {a.user_id} | {'Длительный' if a.duration == AsthmaType.long else 'Короткий'} | {a.reason} | {'Да' if a.inhalation else 'Нет'} | {a.comment or ''} |\n"
                        )
                with open(md_path, "rb") as f:
                    await update.message.reply_document(f, filename="asthma_attacks_export.md")
        elif export_type == "defecation":
            result = await session.execute(select(Defecation).order_by(Defecation.date_time.asc()))
            defes: List[Defecation] = result.scalars().all()
            headers = ["Дата", "Время", "Пользователь", "Вид стула", "Комментарий"]
            if text == "Выгрузить как CSV":
                import csv

                csv_path = "defecations_export.csv"
                with open(csv_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for d in defes:
                        writer.writerow(
                            [
                                d.date_time.strftime("%Y-%m-%d"),
                                d.date_time.strftime("%H:%M"),
                                d.user_id,
                                d.stool_type.value,
                                d.comment or "",
                            ]
                        )
                with open(csv_path, "rb") as f:
                    await update.message.reply_document(f, filename="defecations_export.csv")
            elif text == "Выгрузить как сообщение":
                msg = []
                for d in defes:
                    msg.append(
                        f"Дата: {d.date_time.strftime('%Y-%m-%d')}\n"
                        f"Время: {d.date_time.strftime('%H:%M')}\n"
                        f"Пользователь: {d.user_id}\n"
                        f"Вид стула: {d.stool_type.value}\n"
                        f"Комментарий: {d.comment or '-'}\n"
                        f"---"
                    )
                text_out = "\n".join(msg) if msg else "Нет данных."
                await update.message.reply_text(text_out)
            elif text == "Выгрузить как markdown-файл":
                md_path = "defecations_export.md"
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("| " + " | ".join(headers) + " |\n")
                    f.write("|" + "---|" * len(headers) + "\n")
                    for d in defes:
                        f.write(
                            f"| {d.date_time.strftime('%Y-%m-%d')} | {d.date_time.strftime('%H:%M')} | {d.user_id} | {d.stool_type.value} | {d.comment or ''} |\n"
                        )
                with open(md_path, "rb") as f:
                    await update.message.reply_document(f, filename="defecations_export.md")

    await engine.dispose()
    await update.message.reply_text("Готово! Все данные у вас. Что делаем дальше? 🐾", reply_markup=main_keyboard)
    context.user_data.clear()
    return MAIN_MENU


def main() -> None:
    """Точка входа: инициализация БД и запуск Telegram-бота."""
    init_db()
    persistence = PicklePersistence(filepath="bot_state.pickle")
    app: Application = Application.builder().token(str(os.getenv("TELEGRAM_TOKEN"))).persistence(persistence).build()
    conv_handler: ConversationHandler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_type)],
            ASK_ASTHMA_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_duration)],
            ASK_ASTHMA_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_reason)],
            ASK_ASTHMA_INHALATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_inhalation)],
            SAVE_ASTHMA_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, asthma_comment)],
            ASK_DEFE_STOOL_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_defe_stool_type)],
            SAVE_DEFE_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, defe_comment)],
            CHOOSE_EXPORT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_export_type)],
            CHOOSE_EXPORT_FORMAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, export_format)],
        },
        fallbacks=[CommandHandler("start", start)],
        name="main_conv",
        persistent=True,
    )
    app.add_handler(conv_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
