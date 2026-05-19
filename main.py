"""
Bot Telegram - Upload ke MixDrop
Pyrogram + Railway Deploy
"""

import os
import math
import logging
import requests
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# ─── Konfigurasi dari Environment Variable Railway ────────────────────────────
API_ID        = int(os.environ.get("API_ID", "0"))
API_HASH      = os.environ.get("API_HASH", "")
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
MIXDROP_EMAIL = os.environ.get("MIXDROP_EMAIL", "")
MIXDROP_KEY   = os.environ.get("MIXDROP_KEY", "")
MIXDROP_FOLDER = os.environ.get("MIXDROP_FOLDER", "")
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

MIXDROP_API = "https://ul.mixdrop.ag/api"
TMP_DIR     = "/tmp/mixdrop_downloads"
os.makedirs(TMP_DIR, exist_ok=True)

app = Client(
    "mixdrop_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ─── Helper ───────────────────────────────────────────────────────────────────

def fmt_size(size_bytes: int) -> str:
    if not size_bytes:
        return "?"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / 1024 / 1024:.1f} MB"
    return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"


def upload_to_mixdrop(file_path: str, filename: str) -> dict:
    data = {"email": MIXDROP_EMAIL, "key": MIXDROP_KEY}
    if MIXDROP_FOLDER:
        data["folder"] = MIXDROP_FOLDER
    with open(file_path, "rb") as f:
        resp = requests.post(
            MIXDROP_API,
            data=data,
            files={"file": (filename, f)},
            timeout=600
        )
    resp.raise_for_status()
    return resp.json()


def get_mixdrop_link(result: dict):
    ref = (
        result.get("result") or
        result.get("fileref") or
        result.get("ref") or ""
    )
    if ref and isinstance(ref, str) and ref.strip():
        return f"https://mixdrop.ag/f/{ref.strip()}"
    return None


async def safe_edit(status: Message, text: str):
    try:
        await status.edit_text(text)
    except Exception:
        pass


async def progress(current, total, status: Message, label: str):
    if total == 0:
        return
    pct    = current / total * 100
    filled = math.floor(pct / 10)
    bar    = "█" * filled + "░" * (10 - filled)
    await safe_edit(status, f"{label}\n[{bar}] {pct:.1f}%\n{fmt_size(current)} / {fmt_size(total)}")


# ─── Commands ─────────────────────────────────────────────────────────────────

@app.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply(
        "👋 Halo! Aku bot upload MixDrop.\n\n"
        "Kirim file apa saja (sampai 2 GB),\n"
        "aku upload ke MixDrop dan kirim linknya.\n\n"
        "/start — pesan ini\n"
        "/help  — bantuan\n"
        "/info  — info akun"
    )


@app.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    await message.reply(
        "📖 Cara pakai:\n"
        "1. Kirim file ke bot ini\n"
        "2. Tunggu progress download & upload\n"
        "3. Dapat link MixDrop\n\n"
        "✅ Support sampai 2 GB\n"
        "✅ Semua format file"
    )


@app.on_message(filters.command("info"))
async def cmd_info(client, message: Message):
    await message.reply(
        f"⚙️ Akun MixDrop:\n"
        f"Email : {MIXDROP_EMAIL}\n"
        f"Folder: {MIXDROP_FOLDER or '(root)'}"
    )


# ─── File Handler ─────────────────────────────────────────────────────────────

@app.on_message(
    filters.private & (
        filters.document | filters.video | filters.audio |
        filters.photo | filters.voice | filters.video_note |
        filters.animation
    )
)
async def handle_file(client, message: Message):
    if message.document:
        media    = message.document
        filename = media.file_name or f"file_{media.file_unique_id}"
    elif message.video:
        media    = message.video
        filename = media.file_name or f"video_{media.file_unique_id}.mp4"
    elif message.audio:
        media    = message.audio
        filename = media.file_name or f"audio_{media.file_unique_id}.mp3"
    elif message.photo:
        media    = message.photo
        filename = f"photo_{media.file_unique_id}.jpg"
    elif message.voice:
        media    = message.voice
        filename = f"voice_{media.file_unique_id}.ogg"
    elif message.video_note:
        media    = message.video_note
        filename = f"videonote_{media.file_unique_id}.mp4"
    elif message.animation:
        media    = message.animation
        filename = media.file_name or f"anim_{media.file_unique_id}.gif"
    else:
        await message.reply("Format tidak dikenali.")
        return

    file_size  = getattr(media, "file_size", 0) or 0
    size_str   = fmt_size(file_size)
    local_path = os.path.join(TMP_DIR, f"{media.file_unique_id}_{filename}")

    status = await message.reply(f"⏳ Memproses {filename} ({size_str})...")

    try:
        # 1. Download dari Telegram
        await safe_edit(status, f"⬇️ Mengunduh dari Telegram...\n[░░░░░░░░░░] 0%\n0 / {size_str}")
        await client.download_media(
            message,
            file_name=local_path,
            progress=progress,
            progress_args=(status, "⬇️ Mengunduh dari Telegram...")
        )

        if not os.path.exists(local_path):
            await safe_edit(status, "❌ Gagal download dari Telegram.")
            return

        actual_size = fmt_size(os.path.getsize(local_path))

        # 2. Upload ke MixDrop
        await safe_edit(status, f"⬆️ Mengupload ke MixDrop...\n📄 {filename} ({actual_size})\nMohon tunggu...")
        result = upload_to_mixdrop(local_path, filename)
        log.info(f"MixDrop response: {result}")

        link = get_mixdrop_link(result)

        # 3. Kirim hasil
        if link:
            await safe_edit(
                status,
                f"✅ Upload berhasil!\n\n"
                f"📄 File : {filename}\n"
                f"📦 Size : {actual_size}\n"
                f"🔗 Link : {link}"
            )
            try:
                await message.reply(
                    "Tap tombol untuk membuka:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 Buka di MixDrop", url=link)
                    ]])
                )
            except Exception as btn_err:
                log.warning(f"Tombol gagal: {btn_err}")
        else:
            err = result.get("error") or result.get("message") or str(result)
            await safe_edit(status, f"❌ Upload MixDrop gagal:\n{err}\n\nResponse: {result}")

    except requests.exceptions.RequestException as e:
        log.exception("Request error ke MixDrop")
        await safe_edit(status, f"❌ Error koneksi ke MixDrop:\n{e}")
    except Exception as e:
        log.exception("Error saat proses file")
        await safe_edit(status, f"❌ Error: {e}")
    finally:
        if os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("✅ Bot MixDrop berjalan di Railway...")
    app.run()
