"""
entry point for the noted editor
"""

from noted.utils import create_logger
from noted.settings import load_configuration

# from noted.server import launch_server
from noted.app import mainloop, run


logger = create_logger(__name__)
project_settings = load_configuration()

if __name__ == "__main__":
    logger.info("starting mainloop")
    # mainloop(launch_browser=False)
    run()
