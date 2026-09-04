from pydantic import BaseModel, ConfigDict


class ConfigBaseModel(BaseModel):
    # Preserves the config the former agentex.lib.utils.model_utils.BaseModel
    # applied; deployment_config's `global` alias relies on populate_by_name.
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
