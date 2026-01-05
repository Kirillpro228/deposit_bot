import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

TOKEN = "8537456289:AAHt8w0DJvmBDHK3GejHE8qle0G_LmAKTeA"

chat_data = {}

async def is_group_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except TelegramBadRequest:
        return False

def get_chat(chat_id: int):
    if chat_id not in chat_data:
        chat_data[chat_id] = {
            "fee": None,
            "rate": None,
            "deposits": [],
            "payouts": [],
            "state": "wait_fee",
            "pending": None
        }
    return chat_data[chat_id]

def calculate_usd(amount_try, fee, rate):
    return round(amount_try * (1 - fee / 100) / rate, 2)

def main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Depozito Ekle (TRY)", callback_data="add_deposit")
    kb.button(text="➖ Ödeme Ekle (USD)", callback_data="add_payout")
    kb.button(text="📊 Rapor", callback_data="report")
    kb.adjust(1)
    return kb.as_markup()

def confirm_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Onayla", callback_data="confirm")
    kb.button(text="❌ İptal", callback_data="cancel")
    kb.adjust(2)
    return kb.as_markup()

# ───── handlers ─────

async def start_handler(message: Message, bot: Bot):
    # 🔵 Проверка ТОЛЬКО для группы
    if message.chat.type != "private":
        if not await is_group_admin(bot, message.chat.id, message.from_user.id):
            await message.answer("⛔ Bu botu sadece yöneticiler kullanabilir.")
            return

    chat = get_chat(message.chat.id)
    chat.update(state="wait_fee", pending=None)

    await message.answer(
        "👋 Depozito Hesaplama Botu\n\n"
        "📉 Komisyon oranını giriniz (örn: 9.5)"
    )

async def text_handler(message: Message, bot: Bot):
    # 🔵 Ограничение ТОЛЬКО для группы
    if message.chat.type != "private":
        if not await is_group_admin(bot, message.chat.id, message.from_user.id):
            return

    chat = get_chat(message.chat.id)

    try:
        value = float(message.text.replace(",", "."))

        if chat["state"] in ("wait_fee", "wait_rate", "wait_deposit", "wait_payout"):
            chat["pending"] = {
                "type": chat["state"],
                "value": value
            }

            await message.answer(
                f"🔍 Girilen değer: {value}\n\n"
                f"Onaylıyor musunuz?",
                reply_markup=confirm_keyboard()
            )
    except:
        await message.answer("❌ Geçerli bir sayı giriniz")

async def callback_handler(call: CallbackQuery, bot: Bot):
    message = call.message
    chat = get_chat(message.chat.id)

    # 🔵 Ограничение ТОЛЬКО для группы
    if message.chat.type != "private":
        if not await is_group_admin(bot, message.chat.id, call.from_user.id):
            await call.answer("⛔ Sadece yöneticiler", show_alert=True)
            return

    # ── подтверждение / отмена ──
    if call.data in ("confirm", "cancel"):
        pending = chat.get("pending")
        if not pending:
            await call.answer()
            return

        if call.data == "cancel":
            chat["pending"] = None
            await message.answer("❌ İptal edildi. Lütfen tekrar giriniz.")
            await call.answer()
            return

        value = pending["value"]
        ptype = pending["type"]

        if ptype == "wait_fee":
            chat["fee"] = value
            chat["state"] = "wait_rate"
            await message.answer("💱 TRY → USD kurunu giriniz:")

        elif ptype == "wait_rate":
            chat["rate"] = value
            chat["state"] = "ready"
            await message.answer(
                "✅ Ayarlar tamamlandı!",
                reply_markup=main_keyboard()
            )

        elif ptype == "wait_deposit":
            chat["deposits"].append(value)
            chat["state"] = "ready"
            usd = calculate_usd(value, chat["fee"], chat["rate"])
            await message.answer(
                f"✅ Depozito eklendi\nTRY: {value}\nUSD: {usd}",
                reply_markup=main_keyboard()
            )

        elif ptype == "wait_payout":
            chat["payouts"].append(value)
            chat["state"] = "ready"
            await message.answer(
                f"💸 Ödeme eklendi\nUSD: {value}",
                reply_markup=main_keyboard()
            )

        chat["pending"] = None
        await call.answer()
        return

    # ── обычные кнопки ──
    if chat["state"] != "ready":
        await call.answer("⚠️ Önce ayarları tamamlayın", show_alert=True)
        return

    if call.data == "add_deposit":
        chat["state"] = "wait_deposit"
        await message.answer("💰 Depozito tutarını giriniz (TRY):")

    elif call.data == "add_payout":
        chat["state"] = "wait_payout"
        await message.answer("💸 Ödeme tutarını giriniz (USD):")

    elif call.data == "report":
        total_try = sum(chat["deposits"])
        total_usd = sum(calculate_usd(x, chat["fee"], chat["rate"]) for x in chat["deposits"])
        paid = sum(chat["payouts"])
        unpaid = round(total_usd - paid, 2)

        await message.answer(
            f"📊 RAPOR\n\n"
            f"TRY: {total_try}\n"
            f"Komisyon: %{chat['fee']}\n"
            f"Kur: {chat['rate']}\n\n"
            f"Ödenecek: {total_usd} USD\n"
            f"Ödenen: {paid} USD\n"
            f"Kalan: {unpaid} USD",
            reply_markup=main_keyboard()
        )

    await call.answer()

# ───── запуск ─────

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    dp.message.register(start_handler, Command("start"))
    dp.message.register(text_handler, F.text)
    dp.callback_query.register(callback_handler)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
