#!/usr/bin/env python3
import os
import tempfile
import shutil
import requests
from pathlib import Path

from telegram import Update, Bot, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = "@sohrani_obsudim"
RAPID_API_KEY = "0e6dc9b84dmsh2db7c5a936be826p1eca23jsne799cef826f2"
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

user_links = {}

SYSTEM_PROMPT = """Ты — автор Telegram канала "сохрани, обсудим". Канал про моду, инфоповоды и эстетику.

Твой стиль: разговорный, от первого лица, мнение автора, читатель участвует мысленно.

Рубрики (выбери одну подходящую):
- "сохрани это" — для красивого контента
- "обсудим?" — для спорного или интересного
- "это кто вообще одобрил" — для странного/WTF
- "тихо происходит" — для скрытых трендов

Формат поста:
- Начни с рубрики или сильного заявления
- 3-5 предложений от первого лица
- Заканчивай вопросом к читателю или "обсудим?"
- 3-4 хэштега из списка: #сохраниобсудим #сохраниэто #обсудим #тывидела #нудавайчестно #мнение #модасейчас #инфоповод #трендилинет #эстетика #ктоэтоодобрил #спорно #гениальноилипровал #тихопроисходит #скрытыйтренд

Важно: пост должен звучать как мысль которую хочется переслать. Никакого официоза. Только живой текст."""


def generate_caption(instagram_url: str) -> str:
    prompt = f"Напиши пост для канала по этой Instagram ссылке: {instagram_url}\n\nПридумай что там может быть (мода, показ, street style, бренд, тренд) и напиши пост в нужном стиле. Только текст поста, без пояснений."

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 500,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    data = response.json()
    return data["content"][0]["text"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь мне ссылку на Instagram пост — скачаю, напишу подпись и запощу в канал автоматически."
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if "instagram.com" not in text:
        await update.message.reply_text("Это не Instagram ссылка. Попробуй ещё раз.")
        return

    await update.message.reply_text("Скачиваю из Instagram...")
    tmp_dir = tempfile.mkdtemp(prefix="insta_")
    try:
        files = download_media(text, tmp_dir)
        if not files:
            await update.message.reply_text("Не удалось скачать. Попробуй другую ссылку.")
            return

        await update.message.reply_text("Пишу подпись...")
        caption = generate_caption(text)

        await update.message.reply_text("Постю в канал...")
        bot = Bot(token=BOT_TOKEN)
        await post_media(bot, files, caption)

        await update.message.reply_text("Готово! Опубликовано в @sohrani_obsudim\n\nВот подпись которую написала:\n\n" + caption)
    except Exception as e:
        await update.message.reply_text("Ошибка: " + str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def download_media(url, tmp_dir):
    response = requests.get(
        "https://instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com/convert",
        params={"url": url},
        headers={
            "x-rapidapi-host": "instagram-downloader-download-instagram-stories-videos4.p.rapidapi.com",
            "x-rapidapi-key": RAPID_API_KEY,
        }
    )
    data = response.json()
    media_list = data.get("media", [])
    files = []
    seen = set()
    for item in media_list[:10]:
        media_url = item.get("thumbnail") or item.get("url")
        media_type = item.get("type", "image")
        if not media_url or media_url in seen:
            continue
        seen.add(media_url)
        r = requests.get(media_url, timeout=30)
        ext = ".mp4" if media_type == "video" else ".jpg"
        filepath = os.path.join(tmp_dir, f"media_{len(files)}{ext}")
        with open(filepath, "wb") as f:
            f.write(r.content)
        files.append(filepath)
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
