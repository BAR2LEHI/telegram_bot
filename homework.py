import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (ConvertJsonError, EmptyApiResponseError,
                        MissingTokenError)

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'logger_hw.log',
    maxBytes=5000000,
    backupCount=5,
    encoding='utf-8'
)
formatter = logging.Formatter(
    '%(asctime)s,'
    '%(levelname)s,'
    '%(message)s,'
    '%(name)s'
)
handler.setFormatter(formatter)
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
    """Проверка наличия переменных окружения."""
    tokens_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for token in tokens_dict:
        if not tokens_dict[token]:
            logger.critical(f'Отсутствует обязательная'
                            f'переменная окружения: {token}')
            return False
    return True


def send_message(bot, message):
    """Отправка сообщение ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Бот успешно отравил сообщение: {message}')
    except Exception as error:
        logger.error(f'Бот не смог отправить сообщение.'
                     f'Текст ошибки: {error}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API Практикум."""
    PAYLOAD = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=PAYLOAD
        )
        if response.status_code != HTTPStatus.OK:
            logger.error('API сервис недоступен')
            raise EmptyApiResponseError('Сервис API недоступен')
    except requests.RequestException:
        logger.error(f'Эндпоинт недоступен.'
                     f'Ответ Api: {response.status_code}')
    try:
        response_json = response.json()
    except Exception:
        raise ConvertJsonError('Не удалось конвертировать'
                               ' json в формат python')
    return response_json


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        raise TypeError('Response пришел не в формате dict')
    if 'current_date' not in response:
        raise KeyError('Отсутствует ключ домашки "current_date"')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ домашки "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Данные ДЗ пришли не в виде списка')
    if not homeworks:
        logger.debug('Список домашнего задания пуст')
    return homeworks


def parse_status(homework):
    """Извлечение данных конкретного ДЗ."""
    if not isinstance(homework, dict):
        raise TypeError('Неверный тип данных homework')
    if 'homework_name' not in homework:
        raise KeyError('У ДЗ отсутствует ключ "homeworks_name"')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('У ДЗ отсутствует ключ "status"')
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise KeyError('Недокументированный статус ДЗ')
    verdict = homework['status']
    return (f'Изменился статус проверки работы "{homework_name}".'
            f'{HOMEWORK_VERDICTS[verdict]}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует обязательная переменная окружения.')
        raise MissingTokenError('Программа принудительно остановлена:'
                                ' отсутствует необходимый токен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                new_message = 'Домашка пока что не проверена'
            else:
                last_homework = homeworks[0]
                new_message = parse_status(last_homework)
            if new_message != prev_message:
                send_message(bot, new_message)
                prev_message = new_message
        except KeyboardInterrupt:
            logger.debug('Программа остановлена принудительно')
        except Exception as error:
            text_error = f'Сбой в работе программы: {error}'
            logger.error(f'Отправка сообщения не удалась: {text_error}')
        finally:
            timestamp = timestamp
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
