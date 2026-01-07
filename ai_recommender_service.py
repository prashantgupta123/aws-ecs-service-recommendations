import json
from typing import Dict, List

from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


async def generate_service_recommendations(
    bedrock_client,
    model_id: str,
    metrics: Dict,
    logs: List[str],
    cluster_name: str,
    service_name: str,
) -> Dict:
    """Generate recommendations for a specific service"""

    service_data = {
        "service_name": service_name,
        "cluster_name": cluster_name,
        "metrics": metrics,
        "logs_count": len(logs),
        "error_logs": [
            log
            for log in logs
            if any(
                keyword in log.lower() for keyword in ["error", "exception", "failed"]
            )
        ],
    }

    # Check if metrics data is available before proceeding
    cpu_data = metrics.get("cpu", [])
    memory_data = metrics.get("memory", [])

    if not cpu_data and not memory_data:
        logger.warning(
            f"No metrics data available for {cluster_name}/{service_name} - using fallback"
        )
        return _fallback_service_recommendations(service_data)

    if not bedrock_client:
        return _fallback_service_recommendations(service_data)

    prompt = f"""
Analyze this ECS service and provide specific recommendations:
Metrics Contains running_count, desired_count, CPU, Memory, Task Definition (cpu, memory, containers etc), Service Scaling Policies (min_capacity, max_capacity) and Target Group (requests, responseTime, httpCode etc) period 1 day for last 7 days.

SERVICE: {service_name} in cluster {cluster_name}
METRICS: {json.dumps(metrics, indent=2)}
ERROR LOGS: {len(service_data['error_logs'])} errors found

Recommendations should focus on: scaling_recommendations, performance_improvements, cost_optimizations, reliability_enhancements, security_best_practices.
Provide JSON response with 5-10 detailed recommendations:
{{
    "service_health": "good|warning|critical",
    "scaling_action": "scale_up|scale_down|no_change",
    "reason": "explanation",
    "recommendations": ["recommendation1", "recommendation2", "recommendation3", "recommendation4", "recommendation5", "recommendation6", "recommendation7", "recommendation8", "recommendation9", "recommendation10"],
    "priority": "low|medium|high"
}}

Focus on actionable insights based on the provided metrics and logs.
Ensure the JSON is properly formatted.
Respond only with the JSON object.
Do not include any additional text or explanations outside the JSON.
"""

    try:
        # Use Bedrock's converse API
        response = bedrock_client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={
                "maxTokens": Config.AI_SERVICE_MAX_TOKENS,
                "temperature": Config.AI_SERVICE_TEMPERATURE,
            },
        )

        ai_response = response["output"]["message"]["content"][0]["text"]

        start_idx = ai_response.find("{")
        end_idx = ai_response.rfind("}") + 1

        if start_idx != -1 and end_idx != -1:
            return json.loads(ai_response[start_idx:end_idx])
    except Exception as e:
        logger.error(f"Error in service recommendations: {e}")

    return _fallback_service_recommendations(service_data)


def _fallback_service_recommendations(service_data: Dict) -> Dict:
    """Fallback recommendations for service"""
    metrics = service_data["metrics"]
    recommendations = []
    health = "good"
    action = "no_change"
    reason = f"Analysis of {service_data['service_name']} metrics and logs"

    # Check if metrics data is available
    cpu_data = metrics.get("cpu", [])
    memory_data = metrics.get("memory", [])

    if not cpu_data and not memory_data:
        health = "warning"
        reason = "Unable to assess service performance due to missing CPU and memory metrics data. The metrics arrays are empty, indicating a potential monitoring issue."
        recommendations.append(
            "Verify CloudWatch metrics collection is enabled for this service"
        )
        recommendations.append(
            "Check IAM permissions for CloudWatch:GetMetricStatistics"
        )
        recommendations.append(
            "Ensure ECS service has proper task definition with awslogs driver"
        )
        return {
            "service_health": health,
            "scaling_action": action,
            "reason": reason,
            "recommendations": recommendations,
            "priority": "medium",
        }

    if cpu_data:
        avg_cpu = sum(dp["Average"] for dp in cpu_data) / len(cpu_data)
        if avg_cpu > Config.CPU_HIGH_THRESHOLD:
            health = "warning"
            action = "scale_up"
            recommendations.append("High CPU usage detected - consider scaling up")

    if memory_data:
        avg_memory = sum(dp["Average"] for dp in memory_data) / len(memory_data)
        if avg_memory > Config.MEMORY_HIGH_THRESHOLD:
            health = "critical" if health == "warning" else "warning"
            action = "scale_up"
            recommendations.append("High memory usage detected - consider scaling up")

    if len(service_data["error_logs"]) > Config.ERROR_LOG_THRESHOLD:
        health = "warning"
        recommendations.append(
            "High error rate in logs - investigate application issues"
        )

    return {
        "service_health": health,
        "scaling_action": action,
        "reason": reason,
        "recommendations": recommendations or ["Service appears healthy"],
        "priority": "high"
        if health == "critical"
        else "medium"
        if health == "warning"
        else "low",
    }
