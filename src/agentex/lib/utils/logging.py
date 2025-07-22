import logging

from rich.console import Console
from rich.logging import RichHandler


def make_logger(name: str):
    """
    Creates a logger object with a RichHandler to print colored text.
    :param name: The name of the module to create the logger for.
    :return: A logger object.
    """
    # Create a console object to print colored text
    console = Console()

    # Create a logger object with the name of the current module
    logger = logging.getLogger(name)

    # Set the global log level to INFO
    logger.setLevel(logging.INFO)

    # Add the RichHandler to the logger to print colored text
    handler = RichHandler(
        console=console,
        show_level=False,
        show_path=False,
        show_time=False,
    )
    logger.addHandler(handler)

    return logger
