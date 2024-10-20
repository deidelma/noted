"""External entry point for the noted package"""

import sys
import time
import webbrowser
from signal import SIGINT, signal

from noted.server import (
    SERVER_URL,
    launch_server,
    remove_crap,
    stop_server,
    update_database_before_exiting,
)
from noted.utils import create_logger

logger = create_logger(__name__)


def interrupt_handler(signal_number, frame) -> None:
    logger.debug("received signal %d from frame %s", signal_number, f"{frame}")
    logger.info("server shutting down")
    stop_server()
    remove_crap()
    logger.info("updating database")
    update_database_before_exiting()
    logger.info("shutdown complete")
    sys.exit(0)


signal(SIGINT, interrupt_handler)


def mainloop(launch_browser: bool = False):
    logger.info("launching server")
    launch_server()
    logger.info("server [%s] launched", SERVER_URL)
    if launch_browser:
        webbrowser.open(f"{SERVER_URL}home")

    # mainloop to allow for process interruption
    while True:
        time.sleep(0.1)


def run():
    """Called to run the server and launch a browser"""
    mainloop(True)


def serve():
    """Called to run the server"""
    mainloop(False)


if __name__ == "__main__":
    mainloop(launch_browser=False)
