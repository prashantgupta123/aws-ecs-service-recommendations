import json
from datetime import datetime
from typing import Any, Dict, List

import boto3

from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


class AIRecommender:
    def __init__(
        self, region: str = Config.AWS_DEFAULT_REGION, aws_session: Any = None
    ):
        account_id = "unknown"
        if aws_session:
            self.bedrock = aws_session.client("bedrock-runtime")
            sts_client = aws_session.client("sts")
            account_id = sts_client.get_caller_identity()["Account"]
        else:
            try:
                self.bedrock = boto3.client("bedrock-runtime", region_name=region)
                sts_client = boto3.client("sts", region_name=region)
                account_id = sts_client.get_caller_identity()["Account"]
            except Exception as e:
                logger.warning(f"Could not initialize Bedrock client: {e}")
                self.bedrock = None
        self.model_name = Config.BEDROCK_MODEL_NAME
        self.model_id = (
            "arn:aws:bedrock:"
            + region
            + ":"
            + account_id
            + ":inference-profile/"
            + self.model_name
        )

    async def generate_recommendations(self, metrics: Dict, logs: Dict) -> Dict:
        """Generate AI-powered recommendations based on metrics and logs"""

        # Prepare data for AI analysis
        analysis_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics_summary": self._summarize_metrics(metrics),
            "log_analysis": self._analyze_logs(logs),
            "clusters": list(metrics.keys()),
        }

        # Create prompt for Bedrock
        prompt = self._create_analysis_prompt(analysis_data)

        # Check if Bedrock is available
        if not self.bedrock:
            logger.warning("Bedrock not available, using fallback recommendations")
            return self._fallback_recommendations(analysis_data)

        try:
            logger.debug(f"Calling Bedrock with model_id: {self.model_id}")
            logger.debug(f"Analysis data clusters: {analysis_data['clusters']}")

            # Use Bedrock's converse API
            response = self.bedrock.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={
                    "maxTokens": Config.AI_MAX_TOKENS,
                    "temperature": Config.AI_TEMPERATURE,
                },
            )

            logger.debug(f"Bedrock response structure: {list(response.keys())}")
            ai_recommendations = response["output"]["message"]["content"][0]["text"]
            logger.debug(f"AI response length: {len(ai_recommendations)}")
            logger.debug(f"AI response preview: {ai_recommendations[:200]}...")

            # Parse and structure recommendations
            recommendations = self._parse_recommendations(
                ai_recommendations, analysis_data
            )
            logger.debug(f"Final recommendations keys: {list(recommendations.keys())}")
            logger.debug(
                f"Overall health: {recommendations.get('overall_health', 'MISSING')}"
            )
            logger.debug(f"Summary: {recommendations.get('summary', 'MISSING')}")

            return recommendations

        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            logger.debug("Using fallback recommendations")
            fallback = self._fallback_recommendations(analysis_data)
            logger.debug(f"Fallback keys: {list(fallback.keys())}")
            return fallback

    def _summarize_metrics(self, metrics: Dict) -> Dict:
        """Summarize metrics for AI analysis"""
        summary = {}

        for cluster, services in metrics.items():
            cluster_summary = {
                "service_count": len(services),
                "high_cpu_services": [],
                "high_memory_services": [],
                "high_response_time_services": [],
                "unhealthy_target_services": [],
                "high_traffic_services": [],
                "avg_cpu": 0,
                "avg_memory": 0,
                "avg_response_time": 0,
                "total_requests": 0,
            }

            total_cpu = 0
            total_memory = 0
            total_response_time = 0
            total_requests = 0
            service_count = 0
            response_time_count = 0

            for service in services:
                service_name = service["service"]
                service_metrics = service["metrics"]
                target_group_metrics = service.get("target_group", {})

                # Analyze CPU
                if service_metrics.get("cpu"):
                    avg_cpu = sum(dp["Average"] for dp in service_metrics["cpu"]) / len(
                        service_metrics["cpu"]
                    )
                    total_cpu += avg_cpu
                    if avg_cpu > 80:
                        cluster_summary["high_cpu_services"].append(service_name)

                # Analyze Memory
                if service_metrics.get("memory"):
                    avg_memory = sum(
                        dp["Average"] for dp in service_metrics["memory"]
                    ) / len(service_metrics["memory"])
                    total_memory += avg_memory
                    if avg_memory > 80:
                        cluster_summary["high_memory_services"].append(service_name)

                # Analyze Target Group Metrics
                for tg_name, tg_data in target_group_metrics.items():
                    # Response Time Analysis
                    if tg_data.get("response_time"):
                        avg_response_time = sum(
                            dp["Average"] for dp in tg_data["response_time"]
                        ) / len(tg_data["response_time"])
                        total_response_time += avg_response_time
                        response_time_count += 1
                        if (
                            avg_response_time > Config.RESPONSE_TIME_THRESHOLD
                        ):  # threshold
                            cluster_summary["high_response_time_services"].append(
                                f"{service_name}({tg_name})"
                            )

                    # Unhealthy Targets Analysis
                    if tg_data.get("unhealthy_hosts"):
                        avg_unhealthy = sum(
                            dp["Average"] for dp in tg_data["unhealthy_hosts"]
                        ) / len(tg_data["unhealthy_hosts"])
                        if avg_unhealthy > 0:
                            cluster_summary["unhealthy_target_services"].append(
                                f"{service_name}({tg_name})"
                            )

                    # Request Volume Analysis
                    if tg_data.get("request_count"):
                        avg_requests = sum(
                            dp["Sum"] for dp in tg_data["request_count"]
                        ) / len(tg_data["request_count"])
                        total_requests += avg_requests
                        if (
                            avg_requests > Config.REQUEST_VOLUME_THRESHOLD
                        ):  # High traffic threshold
                            cluster_summary["high_traffic_services"].append(
                                f"{service_name}({tg_name})"
                            )

                service_count += 1

            if service_count > 0:
                cluster_summary["avg_cpu"] = total_cpu / service_count
                cluster_summary["avg_memory"] = total_memory / service_count
                cluster_summary["total_requests"] = total_requests

            if response_time_count > 0:
                cluster_summary["avg_response_time"] = (
                    total_response_time / response_time_count
                )

            summary[cluster] = cluster_summary

        return summary

    def _analyze_logs(self, logs: Dict) -> Dict:
        """Analyze logs for patterns and issues"""
        analysis = {}

        for cluster, log_messages in logs.items():
            error_count = 0
            warning_count = 0
            common_errors = {}

            for message in log_messages:
                message_lower = message.lower()

                if any(
                    keyword in message_lower
                    for keyword in ["error", "exception", "failed"]
                ):
                    error_count += 1
                    # Extract common error patterns
                    for error_type in [
                        "outofmemory",
                        "connection",
                        "timeout",
                        "permission",
                    ]:
                        if error_type in message_lower:
                            common_errors[error_type] = (
                                common_errors.get(error_type, 0) + 1
                            )

                if any(keyword in message_lower for keyword in ["warning", "warn"]):
                    warning_count += 1

            analysis[cluster] = {
                "total_logs": len(log_messages),
                "error_count": error_count,
                "warning_count": warning_count,
                "common_errors": common_errors,
                "error_rate": error_count / len(log_messages) if log_messages else 0,
            }

        return analysis

    def _create_analysis_prompt(self, data: Dict) -> str:
        """Create prompt for AI analysis"""
        return f"""
You are an AWS ECS infrastructure expert. Analyze the following ECS cluster data and provide specific recommendations:

METRICS SUMMARY:
{json.dumps(data['metrics_summary'], indent=2)}

LOG ANALYSIS:
{json.dumps(data['log_analysis'], indent=2)}

CLUSTERS: {', '.join(data['clusters'])}

Please provide recommendations in the following JSON format:
{{
    "overall_health": "good|warning|critical",
    "scaling_recommendations": [
        {{
            "cluster": "cluster-name",
            "service": "service-name",
            "action": "scale_up|scale_down|no_change",
            "reason": "explanation",
            "suggested_capacity": {{
                "desired_count": number,
                "cpu": number,
                "memory": number
            }}
        }}
    ],
    "performance_issues": [
        {{
            "cluster": "cluster-name",
            "service": "service-name",
            "issue": "description",
            "severity": "low|medium|high",
            "solution": "recommended action"
        }}
    ],
    "cost_optimization": [
        {{
            "cluster": "cluster-name",
            "recommendation": "description",
            "potential_savings": "estimated percentage"
        }}
    ],
    "summary": "Overall assessment and key actions needed"
}}

Focus on:
1. Services with CPU > 80% or Memory > 80% need scaling up
2. Services with CPU < 20% and Memory < 20% might be over-provisioned
3. High error rates in logs indicate application issues
4. Provide specific, actionable recommendations
5. Service with Higher request count and response time should be prioritized for scaling
"""

    def _parse_recommendations(self, ai_response: str, data: Dict) -> Dict:
        """Parse AI response into structured recommendations"""
        logger.debug(f"Parsing AI response of length {len(ai_response)}")

        try:
            # Try to extract JSON from AI response
            start_idx = ai_response.find("{")
            end_idx = ai_response.rfind("}") + 1

            logger.debug(f"JSON boundaries - start: {start_idx}, end: {end_idx}")

            if start_idx != -1 and end_idx != -1:
                json_str = ai_response[start_idx:end_idx]
                logger.debug(f"Extracted JSON: {json_str[:300]}...")

                recommendations = json.loads(json_str)
                logger.debug(f"Parsed JSON keys: {list(recommendations.keys())}")

                recommendations["generated_at"] = data["timestamp"]
                return recommendations
        except Exception as e:
            logger.debug(f"JSON parsing failed: {e}")

        logger.debug("Using fallback recommendations")
        # Fallback parsing
        return self._fallback_recommendations(data)

    def _fallback_recommendations(self, data: Dict) -> Dict:
        """Generate basic recommendations when AI fails"""
        logger.debug("Creating fallback recommendations")
        logger.debug(f"Input data keys: {list(data.keys())}")

        recommendations = {
            "overall_health": "warning",
            "scaling_recommendations": [],
            "performance_issues": [],
            "cost_optimization": [],
            "summary": "Basic analysis completed. Manual review recommended.",
            "generated_at": data.get("timestamp", datetime.now().isoformat()),
        }

        logger.debug(
            f"Base recommendations created with keys: {list(recommendations.keys())}"
        )

        # Generate basic scaling recommendations
        metrics_summary = data.get("metrics_summary", {})
        logger.debug(f"Metrics summary clusters: {list(metrics_summary.keys())}")

        for cluster, summary in metrics_summary.items():
            high_cpu_services = summary.get("high_cpu_services", [])
            logger.debug(
                f"Cluster {cluster} has {len(high_cpu_services)} high CPU services"
            )

            for service in high_cpu_services:
                recommendations["scaling_recommendations"].append(
                    {
                        "cluster": cluster,
                        "service": service,
                        "action": "scale_up",
                        "reason": "High CPU utilization detected",
                        "suggested_capacity": {
                            "desired_count": "increase by 1-2 tasks",
                            "cpu": "consider increasing CPU allocation",
                            "memory": "monitor memory usage",
                        },
                    }
                )

        logger.debug(f"Final fallback recommendations: {recommendations}")
        return recommendations
