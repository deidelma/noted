from noted.app import run
from noted.settings import load_configuration
from noted.utils import create_logger

logger = create_logger(__name__)
project_settings = load_configuration()
logger.info("starting mainloop")
run()
