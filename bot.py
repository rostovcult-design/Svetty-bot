#!/usr/bin/env python3
import os
import re
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

SYSTEM_PROMPT = """Ты — автор Telegram канала "сохрани, обсудим". Канал про моду, инфоповоды и эстетику. Аудитория — девушки.

Твой стиль: живой, разговорный, от первого лица. Обращение к читательнице на "ты" в женском роде ("видела", "знала", "думала"). Текст звучит как сообщение подруге — не рекламный, не официальный, с лёгкой иронией и личным мнением.

Рубрики — выбирай по смыслу контента:
- сохрани это — для красивого, эстетичного контента который хочется сохранить
- обсудим? — для спорного, неоднозначного, интересного инфоповода
- это кто вообще одобрил — для странного, неожиданного, WTF контента
- тихо происходит — для скрытых трендов, тихих изменений в моде

Формат поста (строго соблюдай):

[рубрика — обычный текст]

<b>[эмодзи] [заголовок — конкретный, с именами из поста]</b>

[предложение 1]

[предложение 2]

[предложение 3]

[вопрос к читательнице или "обсудим?"]

<a href="https://www.instagram.com/USERNAME/">@USERNAME</a>

#хэштег1 #хэштег2 #ИмяПерсоны #НазваниеБренда

Правила эмодзи — выбирай разные, по смыслу:
- элегантное/утончённое: 🩰 🎀 🪡 🕶️ 🌹
- громкое/сенсация: 🔥 ⚡️ 💥 👁️
- грустное/конец эпохи: 🖤 🥀 💔 🫖
- арт/культура: 🎭 🖼️ 🫧
- красота/мода: 💅 🪞 👗 💎
- неожиданное/спорное: 👀 🤨 😶 🫠

Правила:
- Каждое предложение основного текста — на отдельной строке с пустой строкой между ними
- Используй ТОЛЬКО теги <b></b> и <a href=""></a>
- НИКОГДА не используй * _ ` [ ] символы
- НИКОГДА не проси дополнительную информацию
- Используй конкретные имена из подписи поста
- Обращайся к читательнице в женском роде
- Хэштеги: 2-3 базовых + имена людей и брендов из поста
- ОБЯЗАТЕЛЬНО меняй рубрику в зависимости от контента"""


def extract_shortcode(url: str) -> str:
    match = re.search(r'/p/([A-Za-z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'/reel/([A-Za-z0-9_-]+)', url)
    if match:
        return match.group(1)
    return ""


def get_post_text(shortcode: str) -> tuple:
    response = requests.get(
        f"https://instagram-api-fast-reliable-data-scraper.p.rapidapi.com/post?shortcode={shortcode}",
        headers={
            "x-rapidapi-host": "instagram-api-fast-reliable-data-scraper.p.rapidapi.com",
            "x-rapidapi-key": RAPID_API_KEY,
        },
        timeout=15
    )
    data = response.json()
    caption_obj = data.get("caption", {})
    if isinstance(caption_obj, dict):
        post_text = caption_obj.get("text", "")
    else:
        post_text = str(caption_obj) if caption_obj else ""
    username = data.get("user", {}).get("username", "")
    return post_text, username


def download_media(url: str, tmp_dir: str) -> list:
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
        media_url = item.get("url") or item.get("thumbnail")
        media_type = item.get("type", "image")
        quality = item.get("quality", "")

        if not media_url or media_url in seen:
            continue

        # Пропускаем thumbnail для видео — берём только HD/SD версии
        if media_type == "video" and quality not in ("HD", "SD", ""):
            continue

        seen.add(media_url)
        r = requests.get(media_url, timeout=60)
        content_type = r.headers.get("content-type", "")

        if "video" in content_type or media_type == "video":
            ext = ".mp4"
        else:
            ext = ".jpg"

        filepath = os.path.join(tmp_dir, f"media_{len(files)}{ext}")
        with open(filepath, "wb") as f:
            f.write(r.content)
        files.append(filepath)

    return files


def generate_caption(post_text: str, username: str) -> str:
    prompt = f"""Оригинальная подпись из Instagram поста от @{username}:

{post_text}

Username источника: {username}

Напиши пост для канала. Вместо USERNAME в теге ссылки используй: {username}
Только текст поста, без пояснений."""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 700,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    data = response.json()
    return data["content"][0]["text"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Отправь мне ссылку на Instagram пост.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "instagram.com" not in text:
        await update.message.reply_text("Это не Instagram ссылка.")
        return

    shortcode = extract_shortcode(text)
    if not shortcode:
        await update.message.reply_text("Не могу найти shortcode.")
        return

    await update.message.reply_text("Скачиваю из Instagram...")
    tmp_dir = tempfile.mkdtemp(prefix="insta_")
    try:
        files = download_media(text, tmp_dir)
        if not files:
            await update.message.reply_text("Не удалось скачать медиа.")
            return

        post_text, username = get_post_text(shortcode)

        await update.message.reply_text("Пишу подпись...")
        caption = generate_caption(post_text, username)

        await update.message.reply_text("Постю в канал...")
        bot = Bot(token=BOT_TOKEN)
        await post_media(bot, files, caption)

        await update.message.reply_text("Готово!")
    except Exception as e:
        await update.message.reply_text("Ошибка: " + str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def is_video(f):
    return Path(f).suffix.lower() in {".mp4", ".mov", ".avi", ".mkv", ".webm"}


async def post_media(bot, files, caption):
    if len(files) == 1:
        f = files[0]
        with open(f, "rb") as fh:
            if is_video(f):
                await bot.send_video(chat_id=CHANNEL, video=fh, caption=caption, parse_mode="HTML", supports_streaming=True)
            else:
                await bot.send_photo(chat_id=CHANNEL, photo=fh, caption=caption, parse_mode="HTML")
    else:
        media, handles = [], []
        for i, f in enumerate(files[:10]):
            fh = open(f, "rb")
            handles.append(fh)
            cap = caption if i == 0 else None
            media.append(InputMediaVideo(fh, caption=cap, parse_mode="HTML") if is_video(f) else InputMediaPhoto(fh, caption=cap, parse_mode="HTML"))
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
