import structlog

from common.core.context import request_id_ctx_var


def add_request_id(_, __, event_dict):
    event_dict["request_id"] = request_id_ctx_var.get()
    return event_dict


structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        add_request_id,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)

def get_logger() -> structlog.PrintLogger:
    logger: structlog.PrintLogger = structlog.get_logger()
    return logger
