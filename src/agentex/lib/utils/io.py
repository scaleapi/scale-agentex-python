from typing import Any

import yaml
from yaml.scanner import ScannerError


class InvalidYAMLError(ValueError):
    """
    Raised when trying to red a YAML file, but the file is not formatted correctly.
    """


def load_yaml_file(file_path: str) -> dict[str, Any]:
    """
    Loads a YAML file from the specified path.

    :param file_path: The path of the YAML file to load.
    :type file_path: str
    :return: The contents of the YAML file.
    :rtype: dict
    """
    try:
        with open(file_path) as file:
            yaml_dict = yaml.safe_load(file)
        return yaml_dict
    except ScannerError as error:
        raise InvalidYAMLError(
            f"The following file is not in valid YAML format: {file_path}"
        ) from error
