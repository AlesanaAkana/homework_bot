import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import StatusCodeError

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='homework.log',
    format='%(asctime)s, %(levelname)s, %(name)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


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


def check_tokens():
    """Проверяет доступность переменных окружения для работы программы."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        return True
    else:
        error_message = 'Ошибка при запросе к API'
        logger.critical(error_message)
        return False


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение в {TELEGRAM_CHAT_ID} отправлено: {message}.')
    except Exception as error:
        error_message = f'Ошибка отправки сообщения в телеграм: {error}'
        logger.error(error_message, exc_info=True)
        raise SystemError(error_message)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        logger.debug('Ответ от API получен.')
        if response.status_code != HTTPStatus.OK:
            error_message = (
                f'Ошибка при запросе к API.'
                f'Статус: {response.status_code}.'
            )
            raise StatusCodeError(error_message)
        return response.json()
    except Exception as error:
        raise SystemError(f'Ошибка при запросе: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Проверка ответа API.')
    if not isinstance(response, dict):
        error_message = 'Ответ от API не словарь.'
        logger.error(error_message)
        raise TypeError(error_message)
    if 'homeworks' not in response:
        error_message = 'В словаре нет ключа "homeworks".'
        logger.error(error_message)
        raise KeyError(error_message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        error_message = 'По ключу "homeworks" не получен список.'
        logger.error(error_message)
        raise TypeError(error_message)
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    logger.debug('Извлекается информация о домашней работе.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None or homework_status is None:
        error_message = 'Неверный ответ от сервера.'
        logger.error(error_message)
        raise KeyError(error_message)
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = 'Неожиданный статус домашней работы.'
        logger.error(error_message)
        raise KeyError(error_message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Не получены токены. Программа остановлена.'
        logger.critical(error_message)
        send_message(chat_id=TELEGRAM_CHAT_ID, text=error_message)
        sys.exit(error_message)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    MESSAGE = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                send_message(bot, parse_status(homework[0]))
            else:
                message = 'Нет новых статусов'
                logger.debug(message)
                raise Exception(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            message_error = str(error)
            if message_error != MESSAGE:
                send_message(bot, message_error)
                MESSAGE = message_error
        finally:
            timestamp = response.get('current_date')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
