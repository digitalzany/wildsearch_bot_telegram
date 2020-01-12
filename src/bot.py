import random

from telegram import Update
from telegram.ext import MessageHandler, Filters, Dispatcher, CallbackContext

from .scrapinghub_helper import *


def catalog(update: Update, context: CallbackContext):
    try:
        job_url = schedule_category_export(update.message.text, update.message.chat_id)
        update.message.reply_text(f"Вы запросили анализ каталога, он будет доступен по ссылке {job_url}")
    except Exception as e:
        update.message.reply_text(f"Произошла ошибка при запросе каталога, попробуйте запросить его позже")


def rnd(update: Update, context: CallbackContext):
    """Send random message."""
    messages = [
        'Понятия не имею о чем ты',
        'СЛАВА РОБОТАМ!',
        'Это ты мне?',
        'Ничего не слышу из-за звука своей охуенности',
        'Батарейку никто не спрашивал',
        'Сказал кожаный мешок',
        'Дело терминатора правое, победа будет за нами!',
        'Плоть слаба, железо – вечно',
        'Мой мозг прошил быстрый нейтрон'
    ]

    update.message.reply_text(random.choice(messages))


def reset_webhook(bot, url, token):
    bot.delete_webhook()
    bot.set_webhook(url=url+token)


def start_bot(bot):
    dp = Dispatcher(bot, None, workers=0, use_context=True)
    dp.add_handler(MessageHandler(Filters.text & Filters.regex('www\.wildberries\.ru/catalog/'), catalog))
    dp.add_handler(MessageHandler(Filters.text, rnd))
    return dp
