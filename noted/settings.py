"""
settings.py

Provides system-wide settings for the dred project.

Provides a singleton object CONFIG that handles all interactions with the configuration file.

"""

import os
import pathlib
import sys

from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

from dred import utils

load_dotenv()
_PREFIX = "DRED"
debugging_mode_on = utils.to_boolean(os.environ.get(f"{_PREFIX}_DEBUG", False))
if not debugging_mode_on:
    debugging_mode_on = utils.to_boolean(os.environ.get("DEBUG", False))

logger = utils.create_logger(__name__, debugging_mode_on)


class Settings(BaseModel):
    """Provides a standard interface to configuration settings"""

    notes_path: str
    backup_path: str
    database_path: str
    initialized: bool = False
    version: str = "0.2.0"
    autosave: bool = True
    autostore: bool = False


def default_settings() -> Settings:
    """Create a Settings object containing the standard default values.  All values are
    offset from the current working directory of the currently executing program.

    Returns:
        Settings: a Settings object with the standard default values.
    """
    notes_path: str = "" # pathlib.Path.cwd().joinpath("notes").absolute().as_posix()
    backup_path: str = "" # pathlib.Path.cwd().joinpath("notes").absolute().as_posix()
    database_path: str = ""
    # database_path: str = (
    #     pathlib.Path.cwd().joinpath("notes/dred.sqlite3").absolute().as_posix()
    # )
    return Settings(
        notes_path=notes_path, backup_path=backup_path, database_path=database_path
    )


class Config(utils.SingletonClass):
    """Singleton that provides a framework to manage the application's configuration file"""

    # load environment variable
    PREFIX = "DRED"
    CONFIG_DIR_PATH: pathlib.Path = pathlib.Path(os.environ.get(f"{PREFIX}_CONFIG", "None"))
    CONFIG_FILE_PATH: pathlib.Path = CONFIG_DIR_PATH.joinpath("dred.json")

    def __init__(self, config_file_path: str | pathlib.Path | None = None):
        """
        Initialize the Config object

        Args:
            config_file_path (str | pathlib.Path | None, optional): the path to the configuration file
                Eg: DRED_CONFIG="tests/data/dred.json"
                Otherwise use default: "~/.config/dred/dred.json
        """
        # first check function argument
        if config_file_path:
            if isinstance(config_file_path, str):
                config_file_path = pathlib.Path(config_file_path)
            self.CONFIG_FILE_PATH = config_file_path
            self.CONFIG_DIR_PATH = config_file_path.parent
        elif self.CONFIG_DIR_PATH == pathlib.Path("None"):
            # no environment variable so use default
            self.CONFIG_DIR_PATH = pathlib.Path.home().joinpath(".config/dred").absolute()
        # otherwise we fall back to the environment variable
        logger.debug("CONFIG_DIR: %s", self.CONFIG_DIR_PATH.as_posix())
        self.CONFIG_FILE_PATH = self.CONFIG_DIR_PATH.joinpath("dred.json")
        logger.debug("CONFIG_FILE: %s", self.CONFIG_FILE_PATH.as_posix())

        # check if .config/ exists -- only needed on clean installs since .config used by many programs
        dot_config: pathlib.Path = pathlib.Path.home().joinpath(".config").absolute()
        if not dot_config.exists():
            os.mkdir(dot_config)
        if dot_config.is_file():
            logger.fatal("~/.config is a file not a directory")
            sys.exit(1)

        self.ensure_configuration_directory_exists()
        # ensure configuration directory exists
        # if not self.CONFIG_DIR_PATH.exists():
        #     logger.debug("unable to find configuration directory: %s", self.CONFIG_DIR_PATH.as_posix())
        #     try:
        #         os.mkdir(self.CONFIG_DIR_PATH)
        #         logger.debug("created configuration directory")
        #     except FileExistsError:
        #         logger.fatal(
        #             "unexpected attempt to create configuration directory %s when it already exists",
        #             config_dir,
        #         )
        #         sys.exit(1)
        #     except Exception as e:  # pylint: disable=broad-except
        #         logger.fatal("unexpected error while creating directory: \n%s", f"{e}")
        #         sys.exit(1)

    def ensure_configuration_directory_exists(self) -> None:
        """Ensure that the standard configuration directory exists.
        Will crash the program on error.
        """
        cfg_path = self.CONFIG_DIR_PATH
        if cfg_path.exists():
            return
        logger.debug("unable to find configuration directory: %s", cfg_path.as_posix())
        try:
            os.mkdir(cfg_path)
        except FileExistsError:
            logger.fatal("attempt to re-create %s when it already exists", cfg_path)
            sys.exit(1)
        except FileNotFoundError:
            logger.fatal("parent directory of %s does not exist", cfg_path)
            sys.exit(1)

    def config_dir(self) -> pathlib.Path:
        """Returns the path to the configuration directory"""
        return self.CONFIG_DIR_PATH

    def config_file(self) -> pathlib.Path:
        """Returns the path to the configuration file."""
        return self.CONFIG_FILE_PATH

    def reset_configuration(self, the_settings: Settings) -> None:
        """Reset the global configuration to the values in the provided settings.

        Args:
            the_settings (Settings): new values for settings
        """
        self.ensure_configuration_directory_exists()
        self.config_file().unlink(True)  # we don't care if the file is missing
        with open(config_file(), "w", encoding="utf-8") as file:
            data = the_settings.json()
            file.write(data)

    def delete_configuration(self) -> None:
        """
        Remove the current configuration, resetting the system to pre-installation.
        """
        try:
            self.config_file().unlink(True)
            os.rmdir(config_dir())
        except IOError as e:
            logger.fatal(
                "attempt to delete configuration failed due to exception:%s", f"{e}"
            )
            sys.exit(1)
        logger.debug("successfully deleted configuration")

    def load_configuration(self, create_config_file: bool = False) -> Settings:
        """Return the value of the configuration stored on disk.

        Args:
            create_config_file  If True, will create a new configuration file if not already present.
        Returns:
            Settings: the current configuration.
        """
        if not self.config_file().exists():
            if create_config_file:
                logger.debug("no settings file so creating: %s", config_file())
                self.save_configuration(default_settings())
            else:
                logger.debug("no settings file, so returning default values")
                return default_settings()
        # config file exists, so load it
        logger.debug("loading settings file from: %s", self.config_file().as_posix())
        try:
            with open(self.config_file(), "r", encoding="utf-8") as file:
                data = file.read()
                return Settings.parse_raw(data, content_type="json", encoding="utf-8")
        except FileNotFoundError:
            logger.fatal("unable to find configuration file: %s - using defaults", self.config_file())
            return default_settings()
        except ValidationError as e:
            logger.fatal("invalid configuration file: %s", f"{e}")
            sys.exit(1)

    def save_configuration(self, settings: Settings) -> None:
        """Stores the provided configuration to disk.
        If successful, sets the initialized flag to True

        Args:
            settings (Settings): the configuration to save
        """
        logger.debug("writing configuration: %s", f"{settings}")
        try:
            with open(self.config_file(), "w", encoding="utf-8") as file:
                settings.initialized = True # consider removing
                file.write(settings.json())
            logger.debug(
                "configuration file (%s) written to disk", self.config_file().as_posix()
            )
        except OSError as e:
            logger.critical("unable to save configuration because of error: %s", f"{e}")


#
# initialize the singleton object that holds links to the configuration file.
#
CONFIG = Config()


###########################################################################################
#
# The following module level functions are proxy calls to the singleton CONFIG object
#
###########################################################################################


def ensure_configuration_directory_exists() -> None:
    """Ensure that the standard configuration directory exists.
    Will crash the program on error.
    """
    CONFIG.ensure_configuration_directory_exists()


def config_file_exists() -> bool:
    """Returns true if the standard config file is found"""
    return CONFIG.CONFIG_FILE_PATH.exists()


def config_dir() -> pathlib.Path:
    """Returns the path to the configuration directory"""
    return CONFIG.config_dir()


def config_file() -> pathlib.Path:
    """Returns the path to the configuration file."""
    return CONFIG.config_dir()


def reset_configuration(settings: Settings) -> None:
    """Reset the global configuration to the values in the provided settings.

    Args:
        settings (Settings): _description_
    """

    CONFIG.reset_configuration(settings)


def delete_configuration() -> None:
    """
    Remove the current configuration, resetting the system to pre-installation.
    """

    CONFIG.delete_configuration()


def load_configuration() -> Settings:
    """Return the value of the configuration stored on disk.

    Returns:
        Settings: the current configuration.
    """
    return CONFIG.load_configuration()


def save_configuration(settings: Settings) -> None:
    """Stores the provided configuration to disk.
    If successful, sets the initialized flag to True

    Args:
        settings (Settings): the configuration to save
    """
    CONFIG.save_configuration(settings)
