import os
import datetime
import time
import requests
import telegram
from dotenv import load_dotenv
import logging

from telegram import Bot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_HW')
TELEGRAM_TOKEN = os.getenv('TOKEN_TM')
TELEGRAM_CHAT_ID = os.getenv('ID_N')

RETRY_TIME = 60 * 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(funcName)s, %(levelname)s, %(message)s'
)


class TheAnswerIsNot200Error(Exception):
    """Ответ сервера не равен 200."""


class EmptyListError(Exception):
    """Пустой словарь или список."""


class UndocumentedStatusError(Exception):
    """Недокументированный статус."""


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат.
    На вход два параметра: экземпляр класса Bot и строка с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Сообщение в Telegram отправлено: {message}')
    except telegram.TelegramError as telegram_error:
        logging.error(
            f'Сообщение в Telegram не отправлено: {telegram_error}')


def get_api_answer(current_timestamp):
    """Сделать запрос к API, вернуть."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != 200:
        logging.error('Эндпоинт не доступен')
        raise TheAnswerIsNot200Error('Эндпоинт не доступен')
    return response.json()


def check_response(response):
    """
    Проверяет ответ API приведенный к типам данных Python.
    Если ответ API соответствует ожиданиям, то функция должна вернуть список
    домашних работ
    (он может быть и пустым), доступный в ответе API по ключу 'homeworks'
    """
    homeworks = response['homeworks']
    if homeworks is None:
        logging.error('Некорректный ответ сервера')
        raise EmptyListError('Некорректный ответ сервера')
    if type(response.get('homeworks')) != list:
        logging.error('Ошибка, возвращаемый объект по ключу homeworks '
                      'не является списком')
        raise TypeError('Ошибка, возвращаемый объект по ключу homeworks '
                        'не является списком')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря HOMEWORK_STATUSES
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        logging.error(f'Ошибка пустое значение '
                      f'homework_status: {homework_status}')
        raise UndocumentedStatusError(
            f'Ошибка пустое значение homework_status: {homework_status}')
    if homework_name is None:
        logging.error(f'Ошибка пустое значение homework_name: {homework_name}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens_bool = True
    if PRACTICUM_TOKEN is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения:'
                         '"PRACTICUM_TOKEN" Программа остановлена.')
    if TELEGRAM_TOKEN is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения: '
                        '"TELEGRAM_TOKEN" Программа остановлена.')
    if TELEGRAM_CHAT_ID is None:
        tokens_bool = False
        logging.critical('Отсутствует обязательная переменная окружения: '
                        '"TELEGRAM_CHAT_ID" Программа остановлена.')
    return tokens_bool


def main():
    """Основная логика работы бота.
    Последовательность действий должна быть примерно такой:
        Сделать запрос к API.       get_api_answer
        Проверить ответ.            check_response
        Если есть обновления — получить статус работы из обновления
        и отправить сообщение в Telegram.
                                    parse_status(homeworks_info[0])
        Подождать некоторое время и сделать новый запрос.
                                    time.sleep(RETRY_TIME)
    """
    if not check_tokens():
        exit()
    bot = Bot(token=TELEGRAM_TOKEN)
    now = datetime.datetime.now()
    send_message(
        bot,
        f'Я начал свою работу: {now.strftime("%d-%m-%Y %H:%M")}')
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks_info = check_response(response)
            if len(homeworks_info) == 0:
                logging.info('Нет работ на проверку')
            elif len(homeworks_info) > 0:
                message = parse_status(homeworks_info[0])
                send_message(bot, message)
            else:
                logging.debug('Статус не изменился')

            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
