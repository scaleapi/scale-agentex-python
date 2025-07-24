import base64
import json

from agentex.lib.sdk.config.agent_manifest import AgentManifest


# Base 64 encode principal dictionary
def _encode_principal_context(manifest: AgentManifest):
    if manifest.auth is None:
        return None

    principal = manifest.auth.principal
    if principal is None:
        return None

    json_str = json.dumps(principal, separators=(',', ':'))
    encoded_bytes = base64.b64encode(json_str.encode('utf-8'))
    return encoded_bytes.decode('utf-8')
