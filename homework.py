import os
import sys
import http
import requests
import time
import logging
import telegram
from dotenv import load_dotenv
import exceptions

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
    """проверяет доступность переменных окружения."""
    # Такого я не ожидал. Моё решение похоже
    # на танец с бубном на асфальте перед светофором....
    # Ваше решение просто увидеть горит зеленый или красный!
    # Класс! Спасибо!
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        # Логируем сообщение перед отправкой
        logger.info('Сообщение подготовлено к отправке.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        # сбой при отправке сообщения в Telegram (уровень ERROR)
        logger.error(f'Сообщение не отправленно: {error}')
        raise exceptions.TelegramError(error)
    else:
        # удачная отправка любого сообщения в Telegram (уровень DEBUG)
        logger.debug(f'Сообщение отправленно: {message}')


def get_api_answer(timestamp) -> dict:
    """Делает запрос к единственному эндпоинту API-сервиса."""
    # Создаем словарь со всеми параметрами запроса
    timestamp = timestamp or int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'params': {'from_date': timestamp}
    }
    try:
        logging.info('Начинаем подключение к эндпоинту {url}')
        response = requests.get(**request_params)
        if response.status_code != http.HTTPStatus.OK:
            # недоступность эндпоинта (уровень ERROR)
            """Пользуясь случаем хочу у Вас спросить:
            можно ли в файл лога добавлять все параметры?"""
            logger.error('Ответ сервера не является успешным!')
            raise exceptions.WrongAPIResponseCodeError(
                {request_params},
                {response}
            )
        return response.json()
    except Exception as error:
        # недоступность эндпоинта (уровень ERROR)
        logger.error('Во время подключения к эндпоинту произошла'
                     ' непредвиденная ошибка!')
        raise exceptions.ConnectionError(request_params, error)


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
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
    """Извлекает статус о конкретной домашней работе."""
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
    """Основная логика работы программы."""
    # Уважаемый ревьювер!
    # Спасибо! С Вами реально интересно работать!
    # Это не комплемент - это факт
    # Я до первой редакции тоже делал функцию
    # проверки новая/предыдущая запись.
    # Ваш вариант - добавить нечего. Всё четко!
    # Спасибо, за прекрасное ревью!
    if not check_tokens():
        message = (
            'Отсутсвуют обязательные переменные окружения: PRACTICUM_TOKEN,'
            ' TELEGRAM_TOKEN, TELEGRAM_CHAT_ID.'
            ' Программа принудительно остановлена.'
        )
        logger.critical(message)
        sys.exit(message)
    # укажем бот
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logger.debug("Telegram-bot запущен!")
    current_report: dict = {'name': '', 'output': ''}
    prev_report: dict = current_report.copy()
    while True:
        current_timestamp = int(time.time())
        logger.debug("Новый забег бота!")
        try:
            # получаем ответ API
            response = get_api_answer(current_timestamp)
            # если ответ содержательный - получаем первую строку
            new_homeworks = check_response(response)
            # если строка читаема
            if new_homeworks:
                # подготовим текст - сообщение
                current_report['name'] = new_homeworks['homework_name']
                current_report['output'] = parse_status(new_homeworks)
            else:
                current_report['output'] = (
                    f'За период от {current_timestamp} до настоящего момента'
                    ' домашних работ нет.'
                )
            if current_report != prev_report:

                send_message(bot, current_report['output'])
                prev_report = current_report.copy()
            else:
                logging.debug('В ответе нет новых статусов.')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            current_report['output'] = message
            logging.error(message, exc_info=True)
            if current_report != prev_report:
                send_message(bot, current_report['output'])
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
