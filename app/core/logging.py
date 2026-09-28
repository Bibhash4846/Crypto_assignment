import json
import logging
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    # output each log entry as a clean json string for log collectors
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
        }
        # append traceback only when an error/exception is raised
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging() -> None:
    # stream logs to stdout formatted as json
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    # force=True overrides any default handlers uvicorn or python already attached
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)