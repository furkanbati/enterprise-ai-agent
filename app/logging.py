import contextvars
import logging
import uuid


_request_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)


def generate_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(request_id: str) -> contextvars.Token:
    return _request_id.set(request_id)


def reset_request_id(token: contextvars.Token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    def filter(
        self,
        record: logging.LogRecord,
    ) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    logger = logging.getLogger()

    if not logger.handlers:
        handler = logging.StreamHandler()
        logger.addHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "request_id=%(request_id)s | "
        "%(name)s | %(message)s",
    )

    request_id_filter = RequestIdFilter()

    for handler in logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(request_id_filter)

    logger.setLevel(logging.INFO)