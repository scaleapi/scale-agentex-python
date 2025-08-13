import os
import json
import boto3

from agentex.lib.utils.logging import make_logger

logger = make_logger(__name__)


def set_openai_api_key_from_secrets_if_not_available_in_env():
    if not os.environ.get("OPENAI_API_KEY"):
        # Use this code snippet in your app.
        # If you need more information about configurations
        # or implementing the sample code, visit the AWS docs:
        # https://aws.amazon.com/developer/language/python/

        secret_name = "team/EGPML/secret-store-key"
        region_name = "us-west-2"

        # Create a Secrets Manager client
        session = boto3.session.Session(profile_name="ml-admin")
        client = session.client(service_name="secretsmanager", region_name=region_name)

        try:
            secrets_by_name = json.loads(
                client.get_secret_value(SecretId=secret_name)["SecretString"]
            )
            os.environ["OPENAI_API_KEY"] = secrets_by_name["OPENAI_API_KEY"]
        except Exception as e:
            logger.error(f"Error getting secret: {e}")
            # For a list of exceptions thrown, see
            # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
            raise
