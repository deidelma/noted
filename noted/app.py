"""External entry point for the noted package"""
import webbrowser
import time
from signal import SIGINT, signal
from noted.server import launch_server, SERVER_URL, stop_server
from noted.utils import create_logger

logger = create_logger(__name__)


def interrupt_handler(signal_number, frame) -> None:
    logger.debug("received signal %d from frame %s", signal_number, f"{frame}")
    print("\nserver shutting down")
    stop_server()
    print("shutdown complete")
    exit(0)


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
