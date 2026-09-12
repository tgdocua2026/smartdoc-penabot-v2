import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@smartdoc_ua"  # Юзернейм вашого каналу

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

class CalcState(StatesGroup):
    waiting_for_sum = State()
    waiting_for_days = State()
    waiting_for_rate = State()

# Заглушка для Render Web Service (відкриває порт)
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Функція перевірки підписки
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["creator", "administrator", "member"]
    except Exception:
        return False

def get_sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Підписатися на канал", url="https://t.me/smartdoc_ua")],
        [InlineKeyboardButton(text="✅ Я підписався / Перевірити", callback_data="check_sub")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    
    is_sub = await check_subscription(message.from_user.id)
    if not is_sub:
        await message.answer(
            "⚠️ Для користування калькулятором необхідно бути підписаним на наш офіційний канал SmartDoc!",
            reply_markup=get_sub_keyboard()
        )
        return

    await message.answer(
        "Вітаємо! Цей бот допоможе вам розрахувати заборгованість, пеню, 3% річних та інфляційні втрати.\n\n"
        "Введіть суму основного боргу в гривнях (наприклад: 10000 або 15500.50):"
    )
    await state.set_state(CalcState.waiting_for_sum)

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: types.CallbackQuery, state: FSMContext):
    is_sub = await check_subscription(callback.from_user.id)
    if is_sub:
        await callback.message.delete()
        await callback.message.answer(
            "✅ Дякуємо за підписку!\n\n"
            "Введіть суму основного боргу в гривнях (наприклад: 10000 або 15500.50):"
        )
        await state.set_state(CalcState.waiting_for_sum)
    else:
        await callback.answer("❌ Ви все ще не підписалися на канал!", show_alert=True)

@dp.message(CalcState.waiting_for_sum)
async def process_sum(message: types.Message, state: FSMContext):
    try:
        debt_sum = float(message.text.replace(",", "."))
        await state.update_data(debt_sum=debt_sum)
        await message.answer("Введіть кількість днів прострочення (наприклад: 30):")
        await state.set_state(CalcState.waiting_for_days)
    except ValueError:
        await message.answer("⚠️ Будь ласка, введіть коректне число суми:")

@dp.message(CalcState.waiting_for_days)
async def process_days(message: types.Message, state: FSMContext):
    try:
        days = int(message.text)
        await state.update_data(days=days)
        await message.answer(
            "Введіть розмір договірної пені (% за кожен день):\n"
            "(Якщо в договорі пеню не вказано, введіть 0. Зазвичай вказують 0.1)"
        )
        await state.set_state(CalcState.waiting_for_rate)
    except ValueError:
        await message.answer("⚠️ Будь ласка, введіть ціле число днів:")

@dp.message(CalcState.waiting_for_rate)
async def process_rate(message: types.Message, state: FSMContext):
    try:
        daily_rate = float(message.text.replace(",", "."))
        data = await state.get_data()
        
        debt_sum = data['debt_sum']
        days = data['days']
        
        penya = (debt_sum * (daily_rate / 100)) * days
        three_percent = (debt_sum * 3 * days) / 36500
        inflation_rate = 0.006 * (days / 30)
        inflation_losses = debt_sum * inflation_rate
        total_sum = debt_sum + penya + three_percent + inflation_losses
        
        res_text = (
            f"РЕЗУЛЬТАТ РОЗРАХУНКУ СТЯГНЕННЯ:\n\n"
            f"Основний борг: {debt_sum:,.2f} грн\n"
            f"Період: {days} днів\n\n"
            f"Деталізація нарахованих сум:\n"
            f"• Договірна пеня ({daily_rate}%/день): {penya:,.2f} грн\n"
            f"• 3% річних (ст. 625 ЦК України): {three_percent:,.2f} грн\n"
            f"• Інфляційні втрати: {inflation_losses:,.2f} грн\n\n"
            f"УСЬОГО ДО СТЯГНЕННЯ: {total_sum:,.2f} грн\n\n"
            f"Напишіть юристу: @tvydoc_help_bot\n"
            f"Шаблони документів: @smartdoc_ua"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Зробити новий розрахунок", callback_data="check_sub")]
        ])
        
        await message.answer(res_text, reply_markup=kb)
        await state.clear()
    except ValueError:
        await message.answer("⚠️ Будь ласка, введіть число (наприклад: 0.1 або 0):")

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
