import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import ConnectionError, StatusCodeError, TelegramError

load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = os.getenv('RETRY_TIME', 600)


ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения для работы программы."""
    logger.debug('Проверка токенов.')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logger.debug('Началась отправка сообщения.')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(
            f'Сообщение "{message}" отправлено в чат {TELEGRAM_CHAT_ID}.'
        )
    except telegram.error.TelegramError as error:
        logger.error('Ошибка отправки сообщения в Telegram.', exc_info=True)
        raise TelegramError(f'Ошибка отправки сообщения в Telegram: {error}')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    logger.debug('Делаем запрос к API.')
    params = {'from_date': timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        logger.debug('Ответ от API получен.')
        if response.status_code != HTTPStatus.OK:
            raise StatusCodeError(
                f'Ошибка при запросе к API.'
                f'Статус: {response.status_code}.'
            )
        return response.json()
    except Exception as error:
        raise ConnectionError(f'Ошибка при запросе: {error}')


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Проверка ответа от API.')
    if not isinstance(response, dict):
        raise TypeError('Ответ от API не словарь.')
    if 'homeworks' not in response:
        raise KeyError('В словаре нет ключа "homeworks".')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('По ключу "homeworks" не получен список.')
    return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    logger.debug('Извлекается информация о домашней работе.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None or homework_status is None:
        raise KeyError('Неверный ответ от сервера.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main(): # noqa
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Не получены токены. Программа остановлена.'
        logger.critical(error_message)
        send_message(chat_id=TELEGRAM_CHAT_ID, text=error_message)
        sys.exit(error_message)
    while True:
        try:
            bot = telegram.Bot(token=TELEGRAM_TOKEN)
            timestamp = int(time.time())
            MESSAGE = ''
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                send_message(bot, parse_status(homework[0]))
            else:
                message = 'Нет новых статусов.'
                logger.debug(message)
        except StatusCodeError as error:
            logger.error(error, exc_info=True)
        except ConnectionError as error:
            logger.error(error, exc_info=True)
        except TypeError as error:
            logger.error(error, exc_info=True)
        except KeyError as error:
            logger.error(error, exc_info=True)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if message != MESSAGE:
                send_message(bot, message)
                MESSAGE = message
        finally:
            timestamp = response.get('current_date')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='homework.log',
        format='%(asctime)s, %(lineno)s, %(levelname)s, %(name)s, %(message)s'
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    main()
