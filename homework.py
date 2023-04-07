import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

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


def check_tokens():
    """Проверка наличия переменных окружения."""
    if not all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN]):
        logging.critical('No Token!')
        raise ValueError('Нет одного из необходимых токенов')


def send_message(bot, message):
    """Отправка сообщение ботом."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Бот успешно отравил сообщение: {message}')
    except Exception as error:
        logging.error(f'Бот не смог отправить сообщение.'
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
        if response.status_code != 200:
            logging.error('API сервис недоступен')
            raise Exception('Сервис API недоступен')
    except requests.RequestException:
        logging.error(f'Эндпоинт недоступен.'
                      f'Ответ Api: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if not isinstance(response, dict):
        logging.error('Неверный тип данных response')
        raise TypeError('Неверный тип данных response')
    if 'homeworks' not in response:
        logging.error('Отсутствует ключ "homeworks"')
        raise KeyError('Отсутствует ключ "homeworks"')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        logging.error('Неверный тип данных списка "homeworks"')
        raise TypeError('Неверный тип данных списка "homeworks"')
    if not homeworks:
        logging.debug('Список домашнего задания пуст')
    return homeworks


def parse_status(homework):
    """Извлечение данных конкретного ДЗ."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        logging.error('У ДЗ отсутствует ключ "homeworks_name"')
    if homework['status'] not in HOMEWORK_VERDICTS:
        logging.debug('Недокументированный статус ДЗ')
        raise KeyError('Незадокументированный статус ДЗ')
    verdict = homework['status']
    return (f'Изменился статус проверки работы "{homework_name}".'
            f'{HOMEWORK_VERDICTS[verdict]}')


def main():
    """Основная логика работы бота."""
    check_tokens()
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
                logging.debug(f'Бот успешно отправил сообщение: {new_message}')
                prev_message = new_message
        except Exception as error:
            text_error = f'Сбой в работе программы: {error}'
            logging.error(f'Отправка сообщения не удалась: {text_error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='main.log',
        filemode='w',
        format=(
            '%(asctime)s,'
            '%(levelname)s,'
            '%(message)s,'
            '%(name)s'
        )
    )
    main()
