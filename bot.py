#!/usr/bin/env python3
import os
import tempfile
import shutil
from pathlib import Path

import yt_dlp
from telegram import Update, Bot, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@sohrani_obsudim"
COOKIES = "/app/www.instagram.com_cookies.txt"

user_links = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на Instagram пост и я запощу его в канал."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id not in user_links:
        if "instagram.com" not in text:
            await update.message.reply_text("Это не Instagram ссылка. Попробуй ещё раз.")
            return
        user_links[user_id] = text
        await update.message.reply_text("Напиши подпись для поста (или знак минус чтобы без подписи):")
        return

    caption = "" if text == "-" else text
    url = user_links.pop(user_id)

    await update.message.reply_text("Скачиваю из Instagram...")
    tmp_dir = tempfile.mkdtemp(prefix="insta_")
    try:
        files = download_media(url, tmp_dir)
        if not files:
            await update.message.reply_text("Не удалось скачать. Попробуй другую ссылку.")
            return
        await update.message.reply_text("Постю в канал...")
        bot = Bot(token=BOT_TOKEN)
        await post_media(bot, files, caption)
        await update.message.reply_text("Готово! Опубликовано в @sohrani_obsudim\n\nОтправь следующую ссылку:")
    except Exception as e:
        await update.message.reply_text("Ошибка: " + str(e))
        user_links.pop(user_id, None)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def download_media(url, tmp_dir):
    opts = {
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
               "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
        "cookiefile": COOKIES,
    }
    files = []
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        entries = info.get("entries") or [info]
        for e in entries:
            if e:
                f = ydl.prepare_filename(e)
                if os.path.exists(f):
                    files.append(f)
    return files


def is_video(f):
    return Path(f).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}


async def post_media(bot, files, caption):
    if len(files) == 1:
        f = files[0]
        with open(f, "rb") as fh:
            if is_video(f):
                await bot.send_video(chat_id=CHANNEL, video=fh, caption=caption, supports_streaming=True)
            else:
                await bot.send_photo(chat_id=CHANNEL, photo=fh, caption=caption)
    else:
        media, handles = [], []
        for i, f in enumerate(files[:10]):
            fh = open(f, "rb")
            handles.append(fh)
            cap = caption if i == 0 else None
            media.append(InputMediaVideo(fh, caption=cap) if is_video(f) else InputMediaPhoto(fh, caption=cap))
        try:
            await bot.send_media_group(chat_id=CHANNEL, media=media)
        finally:
            for fh in handles:
                fh.close()


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
