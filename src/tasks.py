import io
import logging

import boto3
from celery import Celery
from envparse import env
from telegram import Bot

from .scrapinghub_helper import WbCategoryComparator, WbCategoryStats, wb_category_export

env.read_envfile()

celery = Celery('tasks')
celery.conf.update(
    broker_url=env('REDIS_URL'),
    task_always_eager=env('CELERY_ALWAYS_EAGER', cast=bool, default=False),
    task_serializer='pickle',  # we transfer binary data like photos or voice messages,
    accept_content=['pickle'],
)

# включаем логи
logger = logging.getLogger(__name__)

bot = Bot(env('TELEGRAM_API_TOKEN'))
s3 = boto3.client('s3')


def get_cat_update_users():
    return env('WILDSEARCH_TEST_USER_LIST').split(',')


@celery.task()
def calculate_wb_category_diff():
    comparator = WbCategoryComparator()
    comparator.load_from_api()
    comparator.calculate_diff()

    added_count = comparator.get_categories_count('added')
    removed_count = comparator.get_categories_count('removed')

    added_unique_count = comparator.get_categories_unique_count('added')

    if added_unique_count == 0:
        message = f'За последние сутки на Wildberries не добавилось категорий'
        files = None
    else:
        comparator.dump_to_s3_file('added')
        comparator.dump_to_s3_file('removed')
        files = [
            comparator.get_s3_file_name('added'),
            comparator.get_s3_file_name('removed'),
        ]

        message = f"""
            Обновились данные по категориям на Wildberries. C последнего  обновления добавилось
            {added_count} категорий, из них {added_unique_count} уникальных. Скрылось
            {removed_count} категорий
        """

    for uid in get_cat_update_users():
        send_wb_category_update_message.delay(uid, message, files)


@celery.task()
def calculate_wb_category_stats(job_id, chat_id):
    stats = WbCategoryStats().fill_from_api(job_id)

    message = f"""
        [{stats.get_category_name()}]({stats.get_category_url()})\n
        \n
        Количество товаров: `{stats.get_goods_count()}`\n
        \n
        Самый дорогой: `{"{:,}".format(stats.get_goods_price_max())}` руб.\n
        Самый дешевый: `{"{:,}".format(stats.get_goods_price_min())}` руб.\n
        Средняя цена: `{"{:,}".format(stats.get_goods_price_mean())}` руб.\n
        \n
        Объем продаж: `{"{:,}".format(stats.get_sales_sum())}` руб. (`{"{:,}".format(stats.get_sales_count())}` шт.)\n
        Средние продажи: `{"{:,}".format(stats.get_sales_mean())}` руб. (`{"{:,}".format(stats.get_sales_mean_count())}` шт.)\n
        Медиана продаж: `{"{:,}".format(stats.get_sales_median())}` руб. (`{"{:,}".format(stats.get_sales_median_count())}` шт.)\n
    """

    bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown', disable_web_page_preview=True)

    bot.send_document(
        chat_id=chat_id,
        document=stats.get_category_excel(),
        filename=f'{stats.get_category_name()} на Wildberries.xlsx',
    )


@celery.task()
def schedule_wb_category_export(category_url, chat_id):
    try:
        wb_category_export(category_url, chat_id)
        message = f'🧠Мы обрабатываем ваш запрос. Когда все будет готово, вы получите результат.\n\nБольшие категории (свыше 1 тыс. товаров) могут обрабатываться до одного часа.\n\nМаленькие категории обрабатываются в течение нескольких минут.'
    except Exception:
        message = f'Произошла ошибка при запросе каталога, попробуйте запросить его позже'

        pass

    bot.send_message(chat_id=chat_id, text=message)


@celery.task()
def send_wb_category_update_message(uid, message, files=None):
    if files is None:
        files = []

    bot.send_message(chat_id=uid, text=message)

    for file_name in files:
        memory_file = io.BytesIO()
        s3.download_fileobj(env('AWS_S3_BUCKET_NAME'), file_name, memory_file)
        memory_file.seek(0, 0)
        bot.send_document(chat_id=uid, document=memory_file, filename=file_name)
