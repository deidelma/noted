"""
entry point for the dred editor
"""

from dred.utils import create_logger
from dred.settings import load_configuration

# from dred.server import launch_server
from dred.app import mainloop


logger = create_logger(__name__, debugging=True)
project_settings = load_configuration()

if __name__ == "__main__":
    mainloop(launch_browser=False)
