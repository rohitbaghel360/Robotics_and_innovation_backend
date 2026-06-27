from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base application HTTP exception."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class UnauthorizedError(AppException):
    def __init__(self, detail: str = "Invalid credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class ConflictError(AppException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status.HTTP_409_CONFLICT, detail)
