from requests import Response
# Денис, скажите, я не намудрил с исключениями?

class TelegramError(Exception):

    def __init__(self, error):
        """Ошибка отправки телеграм сообщения"""
        self.error = error

    def __str__(self):
        return (f'Ошибка отправки телеграм сообщения: {self.error}')


class WrongAPIResponseCodeError(Exception):
    """наш класс унаследованный от Exceptions"""
    def __init__(self,
                 request_params,
                 response: Response):
        """Ответ сервера не является успешным"""
        self.request_params = request_params
        self.response = response

    def __str__(self):
        return ('Ответ сервера не является успешным:'
                f' request params = {self.request_params};'
                f' http_code = {self.response.status_code};'
                f' reason = {self.response.reason};'
                f' content = {self.response.text}')


class ConnectionError(Exception):
    """наш класс унаследованный от Exceptions"""
    def __init__(self, request_params: dict, error):
        """Во время подключения к эндпоинту произошла непредвиденная ошибка"""
        self.request_params=request_params
        self.error=error

    def __str__(self):
        return (
                'Во время подключения к эндпоинту {url} произошла'
                ' непредвиденная ошибка: {error}'
                ' headers = {headers}; params = {params};'
            ).format(
                error=self.error,
                **self.request_params
            )
