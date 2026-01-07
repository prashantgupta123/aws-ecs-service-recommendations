import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    # AWS Configuration
    AWS_DEFAULT_REGION: str = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")

    # Email Configuration
    EMAIL_SOURCE: str = os.getenv("EMAIL_SOURCE")
    EMAIL_DESTINATION: str = os.getenv("EMAIL_DESTINATION")
    EMAIL_CC: str = os.getenv("EMAIL_CC")

    # Authentication Configuration
    DISABLE_AUTH: bool = os.getenv("DISABLE_AUTH", "false").lower() == "true"
    COGNITO_REGION: str = os.getenv("COGNITO_REGION", "ap-south-1")
    COGNITO_USER_POOL_ID: str = os.getenv("COGNITO_USER_POOL_ID")
    COGNITO_CLIENT_ID: str = os.getenv("COGNITO_CLIENT_ID")

    # Database Configuration
    KNOWLEDGE_TABLE_NAME: str = os.getenv(
        "KNOWLEDGE_TABLE_NAME", "ecs-monitoring-knowledge"
    )
    RECOMMENDATIONS_TABLE_NAME: str = os.getenv(
        "RECOMMENDATIONS_TABLE_NAME", "ecs-service-recommendation"
    )

    # TTL Configuration (in seconds)
    RECOMMENDATIONS_TTL: int = int(
        os.getenv("RECOMMENDATIONS_TTL", "2592000")
    )  # 30 days
    METRICS_TTL: int = int(os.getenv("METRICS_TTL", "604800"))  # 7 days
    CLUSTER_DATA_TTL: int = int(os.getenv("CLUSTER_DATA_TTL", "86400"))  # 24 hours
    LEARNING_DATA_TTL: int = int(os.getenv("LEARNING_DATA_TTL", "7776000"))  # 90 days

    # Monitoring Configuration
    METRICS_PERIOD: int = int(os.getenv("METRICS_PERIOD", "86400"))  # 1 day
    METRICS_DAYS: int = int(os.getenv("METRICS_DAYS", "7"))  # 1 week
    ROLE_SESSION_DURATION: int = int(
        os.getenv("ROLE_SESSION_DURATION", "14400")
    )  # 4 hours
    ECS_BATCH_SIZE: int = int(os.getenv("ECS_BATCH_SIZE", "10"))
    LOG_EVENTS_LIMIT: int = int(os.getenv("LOG_EVENTS_LIMIT", "1000"))

    # Performance Thresholds
    CPU_HIGH_THRESHOLD: float = float(os.getenv("CPU_HIGH_THRESHOLD", "80.0"))
    CPU_LOW_THRESHOLD: float = float(os.getenv("CPU_LOW_THRESHOLD", "20.0"))
    MEMORY_HIGH_THRESHOLD: float = float(os.getenv("MEMORY_HIGH_THRESHOLD", "80.0"))
    MEMORY_LOW_THRESHOLD: float = float(os.getenv("MEMORY_LOW_THRESHOLD", "20.0"))
    RESPONSE_TIME_THRESHOLD: float = float(os.getenv("RESPONSE_TIME_THRESHOLD", "2.0"))
    REQUEST_VOLUME_THRESHOLD: int = int(os.getenv("REQUEST_VOLUME_THRESHOLD", "1000"))
    ERROR_LOG_THRESHOLD: int = int(os.getenv("ERROR_LOG_THRESHOLD", "10"))

    # AI Configuration
    BEDROCK_MODEL_NAME: str = os.getenv(
        "BEDROCK_MODEL_NAME", "apac.anthropic.claude-3-7-sonnet-20250219-v1:0"
    )
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "5000"))
    AI_TEMPERATURE: float = float(os.getenv("AI_TEMPERATURE", "0.1"))
    AI_CHAT_MAX_TOKENS: int = int(os.getenv("AI_CHAT_MAX_TOKENS", "5000"))
    AI_CHAT_TEMPERATURE: float = float(os.getenv("AI_CHAT_TEMPERATURE", "0.1"))
    AI_SERVICE_MAX_TOKENS: int = int(os.getenv("AI_SERVICE_MAX_TOKENS", "5000"))
    AI_SERVICE_TEMPERATURE: float = float(os.getenv("AI_SERVICE_TEMPERATURE", "0.1"))

    # Cron Configuration
    DAILY_RECOMMENDATIONS_CRON_ENABLED: bool = (
        os.getenv("DAILY_RECOMMENDATIONS_CRON_ENABLED", "true").lower() == "true"
    )
    WEEKLY_RECOMMENDATIONS_CRON_ENABLED: bool = (
        os.getenv("WEEKLY_RECOMMENDATIONS_CRON_ENABLED", "true").lower() == "true"
    )
    DAILY_RECOMMENDATIONS_HOUR: int = int(os.getenv("DAILY_RECOMMENDATIONS_HOUR", "7"))
    DAILY_RECOMMENDATIONS_MINUTE: int = int(
        os.getenv("DAILY_RECOMMENDATIONS_MINUTE", "0")
    )
    DAILY_REPORTS_HOUR: int = int(os.getenv("DAILY_REPORTS_HOUR", "9"))
    DAILY_REPORTS_MINUTE: int = int(os.getenv("DAILY_REPORTS_MINUTE", "0"))
    WEEKLY_RECOMMENDATIONS_HOUR: int = int(
        os.getenv("WEEKLY_RECOMMENDATIONS_HOUR", "8")
    )
    WEEKLY_RECOMMENDATIONS_MINUTE: int = int(
        os.getenv("WEEKLY_RECOMMENDATIONS_MINUTE", "0")
    )
    WEEKLY_REPORTS_HOUR: int = int(os.getenv("WEEKLY_REPORTS_HOUR", "10"))
    WEEKLY_REPORTS_MINUTE: int = int(os.getenv("WEEKLY_REPORTS_MINUTE", "0"))

    # Application Configuration
    APP_PORT: int = int(os.getenv("PORT", "8000"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Authentication Configuration
    ROLE_EXTERNAL_ID: str = os.getenv("ROLE_EXTERNAL_ID", "ecs-monitoring-app")

    # Docker Configuration
    DOCKER_HEALTH_CHECK_INTERVAL: int = int(
        os.getenv("DOCKER_HEALTH_CHECK_INTERVAL", "30")
    )
    DOCKER_HEALTH_CHECK_TIMEOUT: int = int(
        os.getenv("DOCKER_HEALTH_CHECK_TIMEOUT", "10")
    )
    DOCKER_HEALTH_CHECK_RETRIES: int = int(
        os.getenv("DOCKER_HEALTH_CHECK_RETRIES", "3")
    )
    DOCKER_HEALTH_CHECK_START_PERIOD: int = int(
        os.getenv("DOCKER_HEALTH_CHECK_START_PERIOD", "40")
    )

    # Monitoring Intervals
    MONITORING_INTERVAL: int = int(os.getenv("MONITORING_INTERVAL", "300"))  # 5 minutes

    # Chat Configuration
    CHAT_HISTORY_LIMIT: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))

    # Log Configuration
    LOG_GROUPS_LIMIT: int = int(os.getenv("LOG_GROUPS_LIMIT", "3"))
    LOG_STREAMS_LIMIT: int = int(os.getenv("LOG_STREAMS_LIMIT", "2"))
    TOTAL_LOGS_LIMIT: int = int(os.getenv("TOTAL_LOGS_LIMIT", "100"))

    # AWS Constants
    ECS_NAMESPACE: str = os.getenv("ECS_NAMESPACE", "AWS/ECS")
    ALB_NAMESPACE: str = os.getenv("ALB_NAMESPACE", "AWS/ApplicationELB")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "ES256")

    # Metric Names
    CPU_METRIC_NAME: str = os.getenv("CPU_METRIC_NAME", "CPUUtilization")
    MEMORY_METRIC_NAME: str = os.getenv("MEMORY_METRIC_NAME", "MemoryUtilization")
    HEALTHY_HOSTS_METRIC: str = os.getenv("HEALTHY_HOSTS_METRIC", "HealthyHostCount")
    UNHEALTHY_HOSTS_METRIC: str = os.getenv(
        "UNHEALTHY_HOSTS_METRIC", "UnHealthyHostCount"
    )
    TARGET_RESPONSE_TIME_METRIC: str = os.getenv(
        "TARGET_RESPONSE_TIME_METRIC", "TargetResponseTime"
    )
    REQUEST_COUNT_METRIC: str = os.getenv("REQUEST_COUNT_METRIC", "RequestCount")
    HTTP_2XX_METRIC: str = os.getenv("HTTP_2XX_METRIC", "HTTPCode_Target_2XX_Count")
    HTTP_3XX_METRIC: str = os.getenv("HTTP_3XX_METRIC", "HTTPCode_Target_3XX_Count")
    HTTP_4XX_METRIC: str = os.getenv("HTTP_4XX_METRIC", "HTTPCode_Target_4XX_Count")
