import os
import http
import requests
import time
import logging
from dotenv import load_dotenv
from telegram import Bot, TelegramError
from telegram.ext import Updater
from json.decoder import JSONDecodeError

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
# Здесь задана глобальная конфигурация для всех логгеров
logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s')
# А тут установлены настройки логгера для текущего файла - homework.py
logger = logging.getLogger(__name__)
# Указываем обработчик логов StreamHandler
logger.addHandler(logging.StreamHandler())


def check_tokens():
    '''
    проверяет доступность переменных окружения,
    которые необходимы для работы программы.
    Если отсутствует хотя бы одна переменная окружения —
    продолжать работу бота нет смысла'''
    variables_check = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')
    error_variables_check = set()
    for token in variables_check:
        if globals()[token] is None:
            error_variables_check.add(token)
    if len(error_variables_check) != 0:
        # отсутствие обязательных переменных окружения
        # во время запуска бота (уровень CRITICAL)
        logger.critical(
            'Ошибка доступности переменных:'
            f'{" ,".join(error_variables_check)}')
        # продолжать работу бота нет смысла
        return False
    # всё хорошо
    return True


def send_message(bot, message):
    '''
    Отправляет сообщение в Telegram чат, определяемый переменной окружения
    TELEGRAM_CHAT_ID. Принимает на вход два параметра:
    экземпляр класса Bot и
    строку с текстом сообщения.
    '''
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        # удачная отправка любого сообщения в Telegram (уровень DEBUG)
        logger.debug(f'Сообщение отправленно: {message}')
    except TelegramError as error:
        # сбой при отправке сообщения в Telegram (уровень ERROR)
        logger.error(f'Сообщение не отправленно: {error}')


def get_api_answer(timestamp) -> dict:
    '''
    Делает запрос к единственному эндпоинту API-сервиса.
    В качестве параметра в функцию передается временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python.
    '''
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != http.HTTPStatus.OK:
            # недоступность эндпоинта (уровень ERROR)
            logger.error('Страница недоступна')
            raise http.exceptions.HTTPError()
        return response.json()
    except requests.exceptions.ConnectionError:
        # любые другие сбои при запросе к эндпоинту (уровень ERROR)
        logger.error('Ошибка подключения')
    except requests.exceptions.RequestException as request_error:
        # любые другие сбои при запросе к эндпоинту (уровень ERROR)
        logger.error(f'Ошибка запроса {request_error}')
    except JSONDecodeError:
        # любые другие сбои при запросе к эндпоинту (уровень ERROR)
        logger.error('Ошибка распознования JSON')


def check_response(response):
    '''
    Проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python.
    '''
    if type(response) is not dict:
        txt_error = 'Полученные данные не словарь!'
        logger.error(txt_error)
        raise TypeError(txt_error)
    if 'current_date' not in response:
        # отсутствие ожидаемых ключей в ответе API (уровень ERROR)
        txt_error = 'Ключ current_date отсутствует!'
        logger.error(txt_error)
        raise KeyError(txt_error)
    if type(response['current_date']) is not int:
        txt_error = ('Объект homeworks не является целым числом'
                     'обозначающим дату в формате unixtime!')
        logger.error(txt_error)
        raise TypeError(txt_error)
    if 'homeworks' not in response:
        # отсутствие ожидаемых ключей в ответе API (уровень ERROR)
        txt_error = 'Ключ homeworks отсутствует'
        logger.error(txt_error)
        raise KeyError(txt_error)
    if type(response['homeworks']) is not list:
        txt_error = 'Объект homeworks не является списком'
        logger.error(txt_error)
        raise TypeError(txt_error)
    # Если записей о работе нет - вернем ПУСТОЙ список
    if response['homeworks'] == []:
        # отсутствие в ответе новых статусов (уровень DEBUG)
        logger.debug('Ответа пока нет!')
        return {}
    # Если записи получены - вернем первую запись
    # для получения результата проверки на
    # выбранную дату
    return response.get('homeworks')[0]


def parse_status(homework):
    '''
    Извлекает из информации о конкретной домашней работе статус
    этой работы. В качестве параметра функция получает только один элемент
    из списка домашних работ. В случае успеха, функция возвращает
    подготовленную для отправки в Telegram строку, содержащую один
    из вердиктов словаря HOMEWORK_VERDICTS.
    ***именно для этой функци передаем только первую запись***
    '''
    if 'status' not in homework:
        # отсутствие ожидаемых ключей в ответе API (уровень ERROR)
        txt_error = 'Ключ status отсутствует в homework'
        logger.error(txt_error)
        raise KeyError(txt_error)
    if 'homework_name' not in homework:
        # отсутствие ожидаемых ключей в ответе API (уровень ERROR)
        txt_error = 'Ключ homework_name отсутствует в homework'
        logger.error(txt_error)
        raise KeyError(txt_error)
    homework_status = homework.get('status')
    homework_name = homework.get('homework_name')
    if homework_status not in HOMEWORK_VERDICTS.keys():
        # неожиданный статус домашней работы,
        # обнаруженный в ответе API (уровень ERROR)
        txt_error = ('Значение статуса не найдено'
                     'в словаре HOMEWORK_VERDICTS')
        logger.error(txt_error)
        raise ValueError(txt_error)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    '''
    Основная логика работы программы.
    Последовательность действий:
    1. Сделать запрос к API.
    2. Проверить ответ.
    3. Если есть обновления — получить статус работы из обновления
    и отправить сообщение в Telegram.
    4. Подождать некоторое время и вернуться в пункт 1.
    '''
    # проверим переменные
    if not check_tokens():
        txt_error = 'Отсутствует одна из переменных!'
        raise ValueError(txt_error)
    # укажем бот
    bot = Bot(token=TELEGRAM_TOKEN)
    # Для получения и обработки входящих сообщений применим класс Updater()
    updater = Updater(token=TELEGRAM_TOKEN)
    while True:
        try:
            # запускаем бота!
            updater.start_polling()
            # получаем ответ API
            response = get_api_answer(0)
            # если ответ содержательный - получаем первую строку
            homework = check_response(response)
            # если строка читаема
            if homework:
                # подготовим текст - сообщение
                message = parse_status(homework)
                # отправляем сообщение
                send_message(bot, message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            # отправляем сообщение об ошибке
            send_message(bot, message)
            # записываем ошибку
            logger.error(message)
        # дрыхнем 10 минут
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
