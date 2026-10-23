import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode

import config
import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("futures-bot")

bot = Bot(token=config.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я слежу за крипто-фьючерсами (топ-10 по капитализации) "
        "и присылаю алерт, когда по монете резко растёт число бычьих "
        "или медвежьих сигналов из новостей/Reddit/CryptoPanic.\n\n"
        "Команды:\n"
        "/status — сколько сигналов собрано по каждой монете за последние сутки"
    )


@dp.message(Command("status"))
async def cmd_status(message: Message):
    coins = db.get_tracked_coins()
    if not coins:
        await message.answer("Пока нет собранных сигналов — сборщик ещё не отработал.")
        return

    lines = []
    for coin in sorted(coins):
        rows = db.get_recent_signals(coin, 24 * 60)
        up = sum(1 for r in rows if r["direction"] == "up")
        down = sum(1 for r in rows if r["direction"] == "down")
        lines.append(f"<b>{coin}</b>: {len(rows)} сигналов (🚀{up} / 🔻{down}) за 24ч")

    await message.answer("\n".join(lines))


async def send_alert(text: str):
    if not config.TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID не задан — алерт не отправлен: %s", text)
        return
    await bot.send_message(chat_id=config.TELEGRAM_CHAT_ID, text=text)


async def start_polling():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(start_polling())
