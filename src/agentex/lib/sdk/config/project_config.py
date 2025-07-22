import os
import re
from pathlib import Path
from typing import Any, TypeVar

import yaml
from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError

T = TypeVar("T")


class ConfigResolutionError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status_code = 400


def _preprocess_template(template_str: str) -> str:
    # Replace $env. and $variables. with unique internal names
    return template_str.replace("{{ $env.", "{{ __special_env__.").replace(
        "{{ $variables.", "{{ __special_variables__."
    )


def _extract_variables_section(raw_config_str: str) -> str:
    # Use regex to extract the variables: ... block (YAML top-level)
    match = re.search(
        r"(^variables:.*?)(^config:|\Z)", raw_config_str, re.DOTALL | re.MULTILINE
    )
    if not match:
        return ""
    return match.group(1)


def ProjectConfigLoader(
    config_path: str, model: type[T] | None = None, env_path: str | None = None
) -> dict[str, Any] | T:
    config_path = Path(config_path)
    env_path = Path(env_path) if env_path else config_path.parent / ".env"
    env = _load_env(env_path)
    raw_config_str = _load_file_as_str(config_path)
    raw_config_str = _preprocess_template(raw_config_str)

    # Extract and render only the variables section
    variables_section_str = _extract_variables_section(raw_config_str)
    env_context = {"__special_env__": env, "__special_variables__": {}}
    try:
        env_only_template = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=False,
        ).from_string(variables_section_str)
        rendered_variables_yaml = env_only_template.render(**env_context)
        variables_dict = yaml.safe_load(rendered_variables_yaml).get("variables", {})
    except Exception as e:
        raise ConfigResolutionError(f"Error rendering variables with $env: {e}") from e
    # Second pass: render the whole config with both __special_env__ and resolved __special_variables__
    full_context = {"__special_env__": env, "__special_variables__": variables_dict}
    rendered_config_str = _jinja_render(raw_config_str, full_context)
    try:
        rendered_config = yaml.safe_load(rendered_config_str)
    except Exception as e:
        raise ConfigResolutionError(f"Error loading rendered YAML: {e}") from e
    if "config" not in rendered_config:
        raise ConfigResolutionError("Missing 'config' section in config file.")
    config_section = rendered_config["config"]
    if model is not None:
        return model(**config_section)
    return config_section


def _load_env(env_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _load_file_as_str(path: Path) -> str:
    with open(path) as f:
        return f.read()


def _jinja_render(template_str: str, context: dict) -> str:
    try:
        env = Environment(
            loader=BaseLoader(),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
            autoescape=False,
        )
        template = env.from_string(template_str)
        return template.render(**context)
    except TemplateError as e:
        raise ConfigResolutionError(f"Jinja template error: {e}") from e
