import boto3

from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


def get_aws_session(
    region_name,
    profile_name="",
    role_arn="",
    access_key="",
    secret_key="",
    session_token="",
):
    if profile_name:
        logger.debug(f"Using AWS profile: {profile_name} in region {region_name}")
        session = boto3.session.Session(
            profile_name=profile_name, region_name=region_name
        )
    elif role_arn:
        logger.debug(f"Assuming role: {role_arn} in region {region_name}")
        session_name = "AssumedRoleSession"
        try:
            sts_client = boto3.client("sts", region_name=region_name)
            logger.debug("STS client created, attempting to assume role")
            assumed_role = sts_client.assume_role(
                RoleArn=role_arn,
                RoleSessionName=session_name,
                DurationSeconds=Config.ROLE_SESSION_DURATION,
                ExternalId=Config.ROLE_EXTERNAL_ID,
            )
            logger.debug(
                f"Role assumed successfully, expiration: {assumed_role['Credentials']['Expiration']}"
            )
            aws_temp_access_key_id = assumed_role["Credentials"]["AccessKeyId"]
            aws_temp_secret_access_key = assumed_role["Credentials"]["SecretAccessKey"]
            aws_temp_session_token = assumed_role["Credentials"]["SessionToken"]
            session = boto3.session.Session(
                aws_access_key_id=aws_temp_access_key_id,
                aws_secret_access_key=aws_temp_secret_access_key,
                aws_session_token=aws_temp_session_token,
                region_name=region_name,
            )
            logger.debug("Session created with assumed role credentials")
        except Exception as e:
            logger.error(f"Failed to assume role {role_arn}: {e}")
            raise e
    elif session_token:
        logger.debug(f"Using session token in region {region_name}")
        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region_name,
        )
    elif access_key:
        logger.debug(f"Using access key in region {region_name}")
        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )
    else:
        logger.debug(f"Using default credentials in region {region_name}")
        session = boto3.session.Session(region_name=region_name)
    return session
