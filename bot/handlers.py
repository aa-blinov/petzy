"""Module with Telegram bot handlers for cat health tracking."""

import csv
import io
from datetime import datetime

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import CallbackContext

from bot.db import (
    clear_user_context,
    db,
    get_user_context,
    is_whitelisted,
    save_asthma_attack,
    save_defecation,
    save_user_context,
)

main_keyboard = ReplyKeyboardMarkup([["Приступ астмы"], ["Дефекация"], ["Выгрузить данные"]], resize_keyboard=True)
datetime_keyboard = ReplyKeyboardMarkup(
    [["Сейчас", "Указать дату"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
)
export_keyboard = ReplyKeyboardMarkup(
    [["Выгрузить приступы астмы"], ["Выгрузить дефекации"], ["В меню"]], resize_keyboard=True
)
format_keyboard = ReplyKeyboardMarkup(
    [["Выгрузить как CSV"], ["Выгрузить как markdown-файл"], ["Выгрузить как сообщение"], ["В меню"]],
    resize_keyboard=True,
)
menu_keyboard = ReplyKeyboardMarkup([["В меню"]], resize_keyboard=True)
comment_keyboard = ReplyKeyboardMarkup([["Пропустить"], ["В меню"]], resize_keyboard=True)
stool_type_keyboard = ReplyKeyboardMarkup([["Обычный", "Твердый", "Жидкий"], ["В меню"]], resize_keyboard=True)


async def start(update: Update, context: CallbackContext) -> int:
    """Start command handler."""
    user_id = update.effective_user.id
    if not is_whitelisted(user_id):
        await update.message.reply_text("Вы не в белом списке. Обратитесь к администратору.")
        return -1
    clear_user_context(user_id)
    await update.message.reply_text(
        "Привет! Я помогу вам следить за здоровьем Саймона 🐾. Что запишем?", reply_markup=main_keyboard
    )
    return 0


async def ask_type(update: Update, context: CallbackContext) -> int:
    """Handler for choosing event type (asthma, defecation, export)."""
    text = update.message.text
    user_id = update.effective_user.id
    clear_user_context(user_id)

    if text == "Приступ астмы":
        context.user_data["event_type"] = "asthma"
        await update.message.reply_text("Когда произошёл приступ?", reply_markup=datetime_keyboard)
        return 20
    elif text == "Дефекация":
        context.user_data["event_type"] = "defecation"
        await update.message.reply_text("Когда была дефекация?", reply_markup=datetime_keyboard)
        return 21
    elif text == "Выгрузить данные":
        await update.message.reply_text("Что выгружаем?", reply_markup=export_keyboard)
        return 7
    else:
        await update.message.reply_text("Пожалуйста, выберите действие с помощью кнопок.", reply_markup=main_keyboard)
        return 0


async def ask_event_datetime(update: Update, context: CallbackContext) -> int:
    """Обработка выбора времени события (Сейчас/Указать дату) для приступа астмы."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if text == "Сейчас":
        context.user_data["event_datetime"] = datetime.now()
        await update.message.reply_text(
            "Какой это был приступ у котика? 😿",
            reply_markup=ReplyKeyboardMarkup(
                [["Короткий", "Длительный"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )
        return 1
    elif text == "Указать дату":
        await update.message.reply_text("Пожалуйста, введите дату в формате ДД-ММ-ГГГГ", reply_markup=menu_keyboard)
        context.user_data["awaiting_event_date"] = True
        return 22
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите вариант с помощью кнопок.", reply_markup=datetime_keyboard
        )
        return 20


async def handle_event_date_input(update: Update, context: CallbackContext) -> int:
    """Обработка текстового ввода даты для приступа астмы."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    try:
        event_date = datetime.strptime(text.strip(), "%d-%m-%Y").date()
    except Exception:
        await update.message.reply_text(
            "Некорректный формат. Введите дату в формате ДД-ММ-ГГГГ", reply_markup=menu_keyboard
        )
        return 22

    context.user_data["event_date"] = event_date
    context.user_data.pop("awaiting_event_date", None)
    await update.message.reply_text("Теперь введите время в формате ЧЧ:ММ", reply_markup=menu_keyboard)
    context.user_data["awaiting_event_time"] = True
    return 23


async def handle_event_time_input(update: Update, context: CallbackContext) -> int:
    """Обработка текстового ввода времени для приступа астмы."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    event_date = context.user_data.get("event_date")
    try:
        event_time = datetime.strptime(text.strip(), "%H:%M").time()
    except Exception:
        await update.message.reply_text(
            "Некорректный формат. Введите время в формате ЧЧ:ММ", reply_markup=menu_keyboard
        )
        return 23

    event_dt = datetime.combine(event_date, event_time)
    context.user_data["event_datetime"] = event_dt
    context.user_data.pop("awaiting_event_time", None)
    context.user_data.pop("event_date", None)
    await update.message.reply_text(
        "Какой это был приступ у котика? 😿",
        reply_markup=ReplyKeyboardMarkup(
            [["Короткий", "Длительный"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return 1


async def asthma_duration(update: Update, context: CallbackContext) -> int:
    """Handler for asthma attack duration selection."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if text not in ["Короткий", "Длительный"]:
        await update.message.reply_text(
            'Пожалуйста, выберите "Короткий" или "Длительный" 😿.',
            reply_markup=ReplyKeyboardMarkup(
                [["Короткий", "Длительный"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
            ),
        )
        return 1

    save_user_context(user_id, "duration", text)
    event_dt = context.user_data.get("event_datetime", datetime.now())
    save_user_context(user_id, "date_time", event_dt)

    reason_keyboard = ReplyKeyboardMarkup(
        [["Пил после сна", "Другое"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text("Что могло стать причиной? 🧐", reply_markup=reason_keyboard)
    return 2


async def asthma_reason(update: Update, context: CallbackContext) -> int:
    """Handler for specifying the reason for asthma attack."""
    user_id = update.effective_user.id
    reason = update.message.text

    if reason == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if reason == "Другое":
        await update.message.reply_text("Пожалуйста, опишите причину текстом.", reply_markup=menu_keyboard)
        context.user_data["awaiting_custom_reason"] = True
        return 2

    if context.user_data.get("awaiting_custom_reason"):
        custom_reason = reason.strip()
        if not custom_reason:
            await update.message.reply_text(
                "Опишите причину, пожалуйста. Это важно для здоровья Саймона.", reply_markup=menu_keyboard
            )
            return 2
        save_user_context(user_id, "reason", custom_reason)
        context.user_data.pop("awaiting_custom_reason", None)
        inhalation_keyboard = ReplyKeyboardMarkup(
            [["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text("Делали ингаляцию? 💨", reply_markup=inhalation_keyboard)
        return 3

    if not reason or not reason.strip():
        await update.message.reply_text(
            "Опишите причину, пожалуйста. Это важно для здоровья Саймона.", reply_markup=menu_keyboard
        )
        return 2

    save_user_context(user_id, "reason", reason.strip())
    inhalation_keyboard = ReplyKeyboardMarkup([["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("Делали ингаляцию? 💨", reply_markup=inhalation_keyboard)
    return 3


async def asthma_inhalation(update: Update, context: CallbackContext) -> int:
    """Handler for inhalation question after asthma attack."""
    user_id = update.effective_user.id
    inhalation = update.message.text

    if inhalation == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if inhalation is None or inhalation.lower() not in ["да", "нет"]:
        inhalation_keyboard = ReplyKeyboardMarkup(
            [["Да", "Нет"], ["В меню"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text('Нужно выбрать "Да" или "Нет" 🙏.', reply_markup=inhalation_keyboard)
        return 3

    save_user_context(user_id, "inhalation", inhalation.lower() == "да")
    await update.message.reply_text("Хотите добавить комментарий? 📝", reply_markup=comment_keyboard)
    return 4


async def asthma_comment(update: Update, context: CallbackContext) -> int:
    """Handler for adding a comment to asthma attack event."""
    user_id = update.effective_user.id
    comment = update.message.text

    if comment == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    data = get_user_context(user_id)
    data["comment"] = comment
    save_asthma_attack(user_id, data)
    clear_user_context(user_id)
    await update.message.reply_text("Записал! Надеюсь, Саймону уже лучше. ❤️‍🩹", reply_markup=main_keyboard)
    return 0


async def ask_defe_event_datetime(update: Update, context: CallbackContext) -> int:
    """Обработка выбора времени события (Сейчас/Указать дату) для дефекации."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if text == "Сейчас":
        context.user_data["event_datetime"] = datetime.now()
        await update.message.reply_text("Какой был стул у Саймона? 🚽", reply_markup=stool_type_keyboard)
        return 5
    elif text == "Указать дату":
        await update.message.reply_text("Пожалуйста, введите дату в формате ДД-ММ-ГГГГ", reply_markup=menu_keyboard)
        context.user_data["awaiting_event_date"] = True
        return 24
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите вариант с помощью кнопок.", reply_markup=datetime_keyboard
        )
        return 21


async def handle_defe_event_date_input(update: Update, context: CallbackContext) -> int:
    """Обработка текстового ввода даты для дефекации."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    try:
        event_date = datetime.strptime(text.strip(), "%d-%m-%Y").date()
    except Exception:
        await update.message.reply_text(
            "Некорректный формат. Введите дату в формате ДД-ММ-ГГГГ", reply_markup=menu_keyboard
        )
        return 24

    context.user_data["event_date"] = event_date
    context.user_data.pop("awaiting_event_date", None)
    await update.message.reply_text("Теперь введите время в формате ЧЧ:ММ", reply_markup=menu_keyboard)
    context.user_data["awaiting_event_time"] = True
    return 25


async def handle_defe_event_time_input(update: Update, context: CallbackContext) -> int:
    """Обработка текстового ввода времени для дефекации."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    event_date = context.user_data.get("event_date")
    try:
        event_time = datetime.strptime(text.strip(), "%H:%M").time()
    except Exception:
        await update.message.reply_text(
            "Некорректный формат. Введите время в формате ЧЧ:ММ", reply_markup=menu_keyboard
        )
        return 25

    event_dt = datetime.combine(event_date, event_time)
    context.user_data["event_datetime"] = event_dt
    context.user_data.pop("awaiting_event_time", None)
    context.user_data.pop("event_date", None)
    await update.message.reply_text("Какой был стул у Саймона? 🚽", reply_markup=stool_type_keyboard)
    return 5


async def ask_defe_stool_type(update: Update, context: CallbackContext) -> int:
    """Handler for selecting stool type for defecation event."""
    user_id = update.effective_user.id
    stool_type = update.message.text

    if stool_type == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if stool_type not in ["Обычный", "Твердый", "Жидкий"]:
        await update.message.reply_text(
            "Пожалуйста, выберите вид стула с помощью кнопок.", reply_markup=stool_type_keyboard
        )
        return 5

    save_user_context(user_id, "stool_type", stool_type)
    event_dt = context.user_data.get("event_datetime", datetime.now())
    save_user_context(user_id, "date_time", event_dt)
    await update.message.reply_text("Хотите добавить комментарий? 📝", reply_markup=comment_keyboard)
    return 6


async def defe_comment(update: Update, context: CallbackContext) -> int:
    """Handler for adding a comment to defecation event."""
    user_id = update.effective_user.id
    comment = update.message.text

    if comment == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    data = get_user_context(user_id)
    data["comment"] = comment
    save_defecation(user_id, data)
    clear_user_context(user_id)
    await update.message.reply_text("Отметил! Чистый лоток - залог здоровья! ✨", reply_markup=main_keyboard)
    return 0


async def ask_export_type(update: Update, context: CallbackContext) -> int:
    """Handler for choosing export type."""
    user_id = update.effective_user.id
    text = update.message.text

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if text == "Выгрузить приступы астмы":
        context.user_data["export_type"] = "asthma"
        await update.message.reply_text("Выберите формат выгрузки:", reply_markup=format_keyboard)
        return 8
    elif text == "Выгрузить дефекации":
        context.user_data["export_type"] = "defecation"
        await update.message.reply_text("Выберите формат выгрузки:", reply_markup=format_keyboard)
        return 8
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите тип выгрузки с помощью кнопок.", reply_markup=export_keyboard
        )
        return 7


async def export_format(update: Update, context: CallbackContext) -> int:
    """Handler for choosing export format."""
    user_id = update.effective_user.id
    text = update.message.text
    export_type = context.user_data.get("export_type")

    if text == "В меню":
        clear_user_context(user_id)
        await update.message.reply_text("Хорошо, возвращаемся в главное меню 🐾", reply_markup=main_keyboard)
        return 0

    if export_type == "asthma":
        collection = db["asthma_attacks"]
        title = "Приступы астмы"
    elif export_type == "defecation":
        collection = db["defecations"]
        title = "Дефекации"
    else:
        await update.message.reply_text("Ошибка: не выбран тип выгрузки.", reply_markup=main_keyboard)
        return 0

    records = list(collection.find({"user_id": user_id}).sort("date_time", -1))
    if not records:
        await update.message.reply_text(f"Нет данных для выгрузки ({title}).", reply_markup=main_keyboard)
        return 0

    if export_type == "asthma":
        fields = [
            ("date_time", "Дата и время"),
            ("duration", "Длительность"),
            ("reason", "Причина"),
            ("inhalation", "Ингаляция"),
            ("comment", "Комментарий"),
        ]
    else:
        fields = [
            ("date_time", "Дата и время"),
            ("stool_type", "Тип стула"),
            ("comment", "Комментарий"),
        ]

    for r in records:
        if isinstance(r.get("date_time"), datetime):
            r["date_time"] = r["date_time"].strftime("%Y-%m-%d %H:%M")
        else:
            r["date_time"] = str(r.get("date_time", ""))

        if r.get("comment", "").strip() in ("", "Пропустить"):
            r["comment"] = "-"

        if export_type == "asthma":
            inh = r.get("inhalation")
            if inh is True:
                r["inhalation"] = "Да"
            elif inh is False:
                r["inhalation"] = "Нет"

    if text == "Выгрузить как CSV":
        output = io.StringIO()
        fieldnames = [ru for _, ru in fields]
        writer = csv.writer(output)
        writer.writerow(fieldnames)
        for r in records:
            writer.writerow([r.get(en, "") for en, _ in fields])
        output.seek(0)
        await update.message.reply_document(
            document=io.BytesIO(output.getvalue().encode("utf-8")),
            filename=f"{title.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            caption=f"{title} (CSV)",
            reply_markup=main_keyboard,
        )
        return 0
    elif text == "Выгрузить как markdown-файл":
        md = f"# {title}\n\n"
        md += "| " + " | ".join(ru for _, ru in fields) + " |\n"
        md += "|" + "---|" * len(fields) + "\n"
        for r in records:
            md += "| " + " | ".join(str(r.get(en, "")) for en, _ in fields) + " |\n"
        await update.message.reply_document(
            document=io.BytesIO(md.encode("utf-8")),
            filename=f"{title.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.md",
            caption=f"{title} (Markdown)",
            reply_markup=main_keyboard,
        )
        return 0
    elif text == "Выгрузить как сообщение":
        msg = f"{title}:\n\n"
        for r in records:
            msg += "\n".join(f"*{ru}*: {r.get(en, '')}" for en, ru in fields) + "\n---\n"
        if len(msg) > 4000:
            await update.message.reply_text(
                "Слишком много данных для сообщения, выберите файл.", reply_markup=main_keyboard
            )
            return 0
        await update.message.reply_text(msg, reply_markup=main_keyboard, parse_mode="Markdown")
        return 0
    else:
        await update.message.reply_text("Пожалуйста, выберите формат с помощью кнопок.", reply_markup=format_keyboard)
        return 8
