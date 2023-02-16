import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv

import requests

import telegram

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Доступность переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    return not all(tokens)


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса.

    Параметры функции:
    timestamp - временная метка
    """
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logger.error('Недоступность эндпоинта')
            raise ConnectionError
    except Exception as error:
        logger.error(f'{error}: Сбои при запросе к эндпоинту')
        raise Exception(f'{error}')
    return response.json()


def check_response(response):
    """Проверка ответа API.

    Параметры функции:
    response - ответ API(тип данных Python)
    """
    if not isinstance(response, dict):
        logger.error(f'{TypeError}: Ожидался dict')
        raise TypeError('Ожидался dict')

    if 'homeworks' not in response:
        raise Exception('Отсутствие ожидаемого ключа homeworks в ответе API')

    if 'current_date' not in response:
        raise Exception('Отсутствие ключа current_date в ответе API')

    if not isinstance(response['homeworks'], list):
        logger.error(f'{TypeError}: Ожидался list')
        raise TypeError('Ожидался list')

    return response


def parse_status(homework):
    """Извлечение информации о конкретной Д/р.
    homework_name - название
    verdict - статус

    Параметры функции:
    homework - последний элемент из списка домашних работ
    """
    try:
        homework_name = homework['homework_name']
    except Exception as error:
        logger.error(f'{error}: Отсутствие ожидаемого ключа')
        raise KeyError('Отсутствие ожидаемого ключа "homework_name"')

    if 'status' not in homework:
        logger.error(f'{KeyError}: Отсутствие ожидаемого ключа')
        raise KeyError('Отсутствие ожидаемого ключа "status"')

    try:
        verdict = HOMEWORK_VERDICTS[homework['status']]
    except Exception as error:
        if not homework['status']:
            logger.error('Под ключом "status" отсутсвует значение')
            raise Exception(f'{error}')
        logger.error(f'{error}: Неожиданный статус домашней работы')
        raise Exception(f'{error}')

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения в Telegram чат.

    Параметры функции:
    bot - экземпляр класса Bot
    message - текст сообщения
    """
    logger.debug('Началась отправка сообщения')

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as error:
        logger.error(f'{error}: Cбой при отправке сообщения')

    logger.debug('Сообщеине отправлено')


def main():
    """Основная логика работы бота."""
    current_message = ''
    if check_tokens():
        logger.critical(
            f'{ValueError}: отсутствуют обязательные переменные окружения'
        )
        sys.exit('Отсутствуют обязательные переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = check_response(get_api_answer(timestamp))
            timestamp = response.get('current_dat')
            if response.get('homeworks'):
                message = parse_status(response['homeworks'][0])
                send_message(bot, message)
                current_message = message
            else:
                logger.debug('Новый статус отсутсвует')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if message != current_message:
                send_message(bot, message)
                current_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
