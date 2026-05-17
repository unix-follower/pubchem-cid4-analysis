from .error_code import ErrorCode


class AppException(Exception):
    def __init__(self, message, error_code=ErrorCode.UNKNOWN):
        super().__init__(message)
        self._error_code = error_code

    @property
    def error_code(self):
        return self._error_code
