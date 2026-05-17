from enum import Enum

from fastapi import status


class ErrorCode(Enum):
    UNKNOWN = -1
    ENTITY_NOT_FOUND = 1
    INVALID_INPUT = 2
    DB_FAILED = 1000
    UNSUPPORTED_ML_MODEL = 2000


def to_http_status_code(error_code: ErrorCode):
    error_code_status_map = {
        ErrorCode.ENTITY_NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ErrorCode.INVALID_INPUT: status.HTTP_400_BAD_REQUEST,
        ErrorCode.UNSUPPORTED_ML_MODEL: status.HTTP_400_BAD_REQUEST,
    }
    return error_code_status_map.get(error_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
