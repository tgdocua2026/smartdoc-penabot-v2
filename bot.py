import logging
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# Токен та канал
BOT_TOKEN = "8134904148:AAEsas3Aae0Qv9bfz0QYqQBHYsjYLKGeA8A"
MAIN_CHANNEL = "@smartdoc_ua"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
logging.basicConfig(level=logging.INFO)

# Стан для введення даних
class CalcState(StatesGroup):
    waiting_for_sum = State()
    waiting_for_days = State()
    waiting_for_rate = State()

# Перевірка підписки на канал
async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=MAIN_CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Підписатися на @smartdoc_ua", url=f"https://t.me/{MAIN_CHANNEL[1:]}")],
        [InlineKeyboardButton(text="✅ Я підписався! Розпочати розрахунок", callback_data="check_sub")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    if await check_subscription(message.from_user.id):
        await message.answer(
            "👋 Вітаємо у юридичному калькуляторі від **@smartdoc_ua**!\n\n"
            "Цей бот розраховує:\n"
            "• Договірну пеню (% за кожен день)\n"
            "• 3% річних (ст. 625 ЦК України)\n"
            "• Інфляційні втрати за період\n\n"
            "👇 **Введіть суму основного боргу (у грн):**\n*(Наприклад: 50000)*",
            parse_mode="Markdown"
        )
        await state.set_state(CalcState.waiting_for_sum)
    else:
        await message.answer(
            "🔒 **Доступ обмежено!**\n\n"
            "Щоб скористатися калькулятором пені та інфляційних втрат, підпишіться на наш канал **@smartdoc_ua**.",
            parse_mode="Markdown",
            reply_markup=sub_keyboard()
        )

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: CallbackQuery, state: FSMContext):
    if await check_subscription(callback.from_user.id):
        await callback.message.delete()
        await callback.message.answer(
            "✅ Дякуємо за підписку!\n\n👇 **Введіть суму основного боргу (у грн):**\n*(Наприклад: 50000)*",
            parse_mode="Markdown"
        )
        await state.set_state(CalcState.waiting_for_sum)
    else:
        await callback.answer("❌ Ви все ще не підписалися на @smartdoc_ua!", show_alert=True)

@dp.message(CalcState.waiting_for_sum)
async def process_sum(message: types.Message, state: FSMContext):
    try:
        debt_sum = float(message.text.replace(",", "."))
        await state.update_data(debt_sum=debt_sum)
        await message.answer("📅 **Введіть кількість днів прострочення:**\n*(Наприклад: 60)*", parse_mode="Markdown")
        await state.set_state(CalcState.waiting_for_days)
    except ValueError:
        await message.answer("⚠️ Будь ласка, введіть число (наприклад: 50000):")

@dp.message(CalcState.waiting_for_days)
async def process_days(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Будь ласка, введіть ціле число днів (наприклад: 60):")
        return
    
    days = int(message.text)
    await state.update_data(days=days)
    await message.answer(
        "⚖️ Введіть розмір договірної пені (% за кожен день):\n"
        "(Якщо в договорі пеню не вказано, введіть 0. Зазвичай вказують 0.1)"
    )
    await state.set_state(CalcState.waiting_for_rate)

@dp.message(CalcState.waiting_for_rate)
async def process_rate(message: types.Message, state: FSMContext):
    try:
        daily_rate = float(message.text.replace(",", "."))
        data = await state.get_data()
        
        debt_sum = data['debt_sum']
        days = data['days']
        
        # Математичний розрахунок
        penya = (debt_sum * (daily_rate / 100)) * days
        three_percent = (debt_sum * 3 * days) / 36500
        
        # Оцінка інфляційних втрат
        inflation_rate = 0.006 * (days / 30)
        inflation_losses = debt_sum * inflation_rate
        
        total_sum = debt_sum + penya + three_percent + inflation_losses
        
        res_text = (
            f"📊 **РЕЗУЛЬТАТ РОЗРАХУНКУ СТЯГНЕННЯ:**\n\n"
            f"🔹 Основний борг: **{debt_sum:,.2f} грн**\n"
            f"🔹 Період: **{days} днів**\n\n"
            f"📈 **Деталізація нарахованих сум:**\n"
            f"• Договірна пеня ({daily_rate}%/день): **{penya:,.2f} грн**\n"
            f"• 3% річних (ст. 625 ЦК України): **{three_percent:,.2f} грн**\n"
            f"• Інфляційні втрати (оцінка Держстату): **{inflation_losses:,.2f} грн**\n\n"
            f"💰 **УСЬОГО ДО СТЯГНЕННЯ:** **{total_sum:,.2f} грн**\n\n"
            f"----------------------------------------\n"
            f"📩 *Потрібен офіційний розрахунок для суду або досудова претензія?*\n"
            f"Напишіть нашому юристу: @tvydoc_help_bot\n"
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
