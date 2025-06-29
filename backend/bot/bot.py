# === ФИНАЛЬНАЯ ВЕРСИЯ bot.py ===

import logging
import re
import asyncio
import os
import uuid
import subprocess
import shutil
from youtube_client import YouTubeClient
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# --- Настройка ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not TELEGRAM_BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Не удалось загрузить токены. Убедитесь, что они есть в .env файле.")
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Состояния диалога ---
GETTING_CONTENT, CHOOSING_FORMAT, WAITING_FOR_URL, ASK_YOUTUBE_UPLOAD = range(4)

# --- Вспомогательные функции ---
def parse_user_input(text: str) -> dict:
    extracted_data = {"tts_text": "", "code_text": "", "top_text": "", "bottom_text": ""}
    text_to_process = text
    top_match = re.search(r'!!!([\s\S]*?)!!!', text_to_process)
    if top_match:
        extracted_data["top_text"] = top_match.group(1).strip()
        text_to_process = text_to_process.replace(top_match.group(0), "", 1)
    bottom_match = re.search(r'@@([\s\S]*?)@@', text_to_process)
    if bottom_match:
        extracted_data["bottom_text"] = bottom_match.group(1).strip()
        text_to_process = text_to_process.replace(bottom_match.group(0), "", 1)
    code_match = re.search(r'\/\/\/[a-zA-Z]*\n?([\s\S]*?)\/\/\/', text_to_process)
    if code_match:
        extracted_data["code_text"] = code_match.group(1).strip()
        text_to_process = text_to_process.replace(code_match.group(0), "", 1)
    extracted_data["tts_text"] = text_to_process.strip()
    return extracted_data

async def cleanup_temp_folders(context: ContextTypes.DEFAULT_TYPE, final_video_path_str: str = None):
    """Функция для очистки временных папок."""
    if final_video_path_str:
        final_video_path = Path(final_video_path_str)
        if final_video_path.parent.exists():
            shutil.rmtree(final_video_path.parent)
            logger.info(f"Временная папка для видео {final_video_path.parent} удалена.")

    if Path("media").exists():
        shutil.rmtree("media")
        logger.info("Временная папка 'media' удалена.")

    context.user_data.clear()

# --- Основная логика бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Привет! Пришлите текст для озвучки, код (внутри ///) и надписи (!!!сверху!!! и @@снизу@@).")
    return GETTING_CONTENT

async def get_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    parsed_data = parse_user_input(user_input)
    if not parsed_data["tts_text"] or not parsed_data["code_text"]:
        await update.message.reply_text("Не удалось найти текст для озвучки или блок кода. Попробуйте снова /start.")
        return GETTING_CONTENT
    context.user_data['content'] = parsed_data
    keyboard = [[InlineKeyboardButton("Шортс (9:16)", callback_data="9:16"), InlineKeyboardButton("Широкоформатное (16:9)", callback_data="16:9")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Отлично! Теперь выберите формат видео:", reply_markup=reply_markup)
    return CHOOSING_FORMAT

async def choose_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chosen_format = query.data
    content = context.user_data.get('content')

    if not content:
        await query.edit_message_text(text="Ошибка. Начните сначала /start")
        return ConversationHandler.END

    await query.edit_message_text(text=f"Принято! Формат: {chosen_format}. Создаю видео...")

    unique_id = uuid.uuid4()
    final_video_dir = Path(f"static/videos/{unique_id}/")
    final_video_dir.mkdir(parents=True, exist_ok=True)
    audio_path = final_video_dir / "audio.mp3"
    final_video_path = final_video_dir / "final_video.mp4"

    try:
        # Генерация аудио
        response = client.audio.speech.create(model="tts-1", voice="alloy", input=content["tts_text"])
        response.stream_to_file(audio_path)

        # Генерация видеоряда Manim
        env = os.environ.copy()
        env["CODE_TEXT"] = content["code_text"]
        env["TOP_TEXT"] = content["top_text"]
        env["BOTTOM_TEXT"] = content["bottom_text"]
        env["RESOLUTION"] = "1080,1920" if chosen_format == "9:16" else "1920,1080"
        manim_command = ["python", "-m", "manim", "animate_code.py", "CodeScene"]
        process = await asyncio.create_subprocess_exec(*manim_command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise Exception(f"Manim завершился с ошибкой: {stderr.decode()}")

        # Динамически формируем путь к выходному файлу Manim
        # В animate_code.py framerate=30, а разрешение (вертикальное) 1920 для 9:16 и 1080 для 16:9
        resolution_folder = "1920p30" if chosen_format == "9:16" else "1080p30"
        search_path = Path(f"media/videos/animate_code/{resolution_folder}")
        found_files = list(search_path.rglob("*.mp4"))
        print(f"[BOT DEBUG] Ищу mp4 в: {search_path.resolve()}")
        if not found_files:
            raise Exception(f"Не удалось найти видеофайл Manim в {search_path}")
        manim_output_file = found_files[0]

        # Склейка аудио и видео
        ffmpeg_command = ['ffmpeg', '-i', str(manim_output_file), '-i', str(audio_path), '-c:v', 'copy', '-c:a', 'aac', '-shortest', str(final_video_path)]
        subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)

        if not final_video_path.exists():
            raise Exception("FFmpeg отработал, но финальный видеофайл не был создан.")

        logger.info(f"Финальное видео создано: {final_video_path}")

        # Отправка видео в Telegram
        await context.bot.send_message(chat_id=query.message.chat_id, text="✅ Ваше видео готово! Сейчас я его отправлю...")
        await context.bot.send_video(
            chat_id=query.message.chat_id, video=open(final_video_path, 'rb'), read_timeout=120, write_timeout=120
        )

        # Сохраняем данные для следующего шага
        context.user_data['final_video_path'] = str(final_video_path)
        context.user_data['video_content'] = content

        # Задаем вопрос про YouTube
        keyboard = [[
            InlineKeyboardButton("Да, загрузить", callback_data="yt_upload_yes"),
            InlineKeyboardButton("Нет, спасибо", callback_data="yt_upload_no")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=query.message.chat_id, text="Загрузить это видео на YouTube?", reply_markup=reply_markup
        )

        return ASK_YOUTUBE_UPLOAD

    except Exception as e:
        logger.error(f"Ошибка при создании видео: {e}", exc_info=True)
        await context.bot.send_message(chat_id=query.message.chat_id, text=f"Произошла ошибка: {e}")
        await cleanup_temp_folders(context, str(final_video_path) if 'final_video_path' in locals() else None)
        return ConversationHandler.END

async def handle_youtube_upload_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data

    final_video_path = context.user_data.get('final_video_path')
    content = context.user_data.get('video_content')

    try:
        if choice == "yt_upload_no":
            await query.edit_message_text(text="Хорошо, загрузка на YouTube отменена.")

        elif choice == "yt_upload_yes":
            if not final_video_path or not content:
                await query.edit_message_text(text="Ошибка, данные о видео утеряны. Начните сначала.")
                return ConversationHandler.END

            await query.edit_message_text(text="Начинаю загрузку на YouTube...")
            youtube_client = YouTubeClient()
            if not youtube_client.is_authorized():
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Ошибка: Авторизация YouTube не найдена. Пожалуйста, сначала выполните команду /youtube_auth.")
            else:
                video_title = content["top_text"] if content["top_text"] else "Видео с кодом"
                video_description = content["tts_text"]
                upload_response = youtube_client.upload_video(
                    file_path=final_video_path, title=video_title, description=video_description, tags=[], privacy_status="private"
                )
                if upload_response and upload_response.get("id"):
                    video_id = upload_response.get("id")
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    await context.bot.send_message(chat_id=query.message.chat_id, text=f"✅ Видео успешно загружено на YouTube!\n\nСсылка: {video_url}")
                else:
                    await context.bot.send_message(chat_id=query.message.chat_id, text="❌ Произошла неизвестная ошибка при загрузке видео на YouTube.")
    finally:
        await cleanup_temp_folders(context, final_video_path)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.")
    await cleanup_temp_folders(context)
    return ConversationHandler.END

async def youtube_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    youtube_client = YouTubeClient()
    if youtube_client.is_authorized():
        await update.message.reply_text("✅ Авторизация в YouTube уже пройдена и активна!")
        return ConversationHandler.END

    auth_url = youtube_client.initiate_authorization()
    context.user_data['youtube_client'] = youtube_client
    await update.message.reply_text(
        "Сейчас начнется ручная авторизация:\n\n"
        "1. Перейдите по ссылке ниже.\n"
        "2. Войдите в Google и дайте разрешение.\n"
        "3. Вас перекинет на страницу с ошибкой - **ЭТО НОРМАЛЬНО**.\n"
        "4. **Скопируйте полный URL** из адресной строки браузера.\n"
        "5. Пришлите скопированный URL сюда в чат."
    )
    escaped_url = auth_url.replace('.', r'\.').replace('-', r'\-').replace('=', r'\=').replace('?',r'\?').replace('&',r'\&')
    await update.message.reply_text(f"`{escaped_url}`", parse_mode='MarkdownV2')
    return WAITING_FOR_URL

async def handle_pasted_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pasted_url = update.message.text
    youtube_client = context.user_data.get('youtube_client')
    if not youtube_client:
        await update.message.reply_text("Произошла ошибка. Пожалуйста, начните сначала: /youtube_auth")
        return ConversationHandler.END

    await update.message.reply_text("Проверяю URL, пожалуйста, подождите...")
    if youtube_client.complete_authorization(pasted_url):
        await update.message.reply_text("✅ Авторизация успешно завершена! Теперь можно загружать видео.")
    else:
        await update.message.reply_text("❌ Не удалось завершить авторизацию. URL недействителен или истек. Попробуйте снова: /youtube_auth")

    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    os.makedirs("static/videos", exist_ok=True)
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    generation_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            GETTING_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_content)],
            CHOOSING_FORMAT: [CallbackQueryHandler(choose_format)],
            ASK_YOUTUBE_UPLOAD: [CallbackQueryHandler(handle_youtube_upload_choice)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True, per_chat=True
    )

    auth_conv = ConversationHandler(
        entry_points=[CommandHandler("youtube_auth", youtube_auth)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_pasted_url)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True, per_chat=True
    )

    application.add_handler(generation_conv)
    application.add_handler(auth_conv)

    application.run_polling()

if __name__ == "__main__":
    main()