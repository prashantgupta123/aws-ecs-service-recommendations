import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

import boto3

from AWSSession import get_aws_session
from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


class ECSMonitor:
    def __init__(
        self,
        region: str = Config.AWS_DEFAULT_REGION,
        access_key: str = "",
        secret_key: str = "",
        profile_name: str = "",
        role_arn: str = "",
        session_token: str = "",
    ):
        self.session = get_aws_session(
            region, profile_name, role_arn, access_key, secret_key, session_token
        )
        self.ecs = self.session.client("ecs")
        self.cloudwatch = self.session.client("cloudwatch")
        self.logs = self.session.client("logs")
        self.elbv2 = self.session.client("elbv2")
        self.autoscaling = self.session.client("application-autoscaling")
        self.clusters = []
        self.last_updated = None
        self.period = Config.METRICS_PERIOD
        self.timedelta_days = Config.METRICS_DAYS

    def _get_all_clusters(self) -> List[str]:
        """Get all clusters with pagination"""
        cluster_arns = []
        next_token = None

        while True:
            params = {}
            if next_token:
                params["nextToken"] = next_token

            response = self.ecs.list_clusters(**params)
            cluster_arns.extend(response.get("clusterArns", []))

            next_token = response.get("nextToken")
            if not next_token:
                break

        return cluster_arns

    def _get_all_services(self, cluster_name: str) -> List[str]:
        """Get all services in a cluster with pagination"""
        service_arns = []
        next_token = None

        while True:
            params = {"cluster": cluster_name}
            if next_token:
                params["nextToken"] = next_token

            response = self.ecs.list_services(**params)
            service_arns.extend(response.get("serviceArns", []))

            next_token = response.get("nextToken")
            if not next_token:
                break

        return service_arns

    async def monitor_clusters(self):
        """Monitor all ECS clusters in parallel"""
        try:
            # Get all clusters with pagination
            cluster_arns = self._get_all_clusters()
            self.clusters = [arn.split("/")[-1] for arn in cluster_arns]

            # Monitor clusters in parallel
            tasks = [self._monitor_cluster(cluster) for cluster in self.clusters]
            await asyncio.gather(*tasks, return_exceptions=True)

            self.last_updated = datetime.now().isoformat()
        except Exception as e:
            logger.error(f"Error monitoring clusters: {e}")

    async def _monitor_cluster(self, cluster_name: str):
        """Monitor individual cluster"""
        try:
            # Get services in cluster with pagination
            service_arns = self._get_all_services(cluster_name)

            for service_arn in service_arns:
                service_name = service_arn.split("/")[-1]
                await self._analyze_service(cluster_name, service_name)

        except Exception as e:
            logger.error(f"Error monitoring cluster {cluster_name}: {e}")

    async def _analyze_service(self, cluster_name: str, service_name: str):
        """Analyze service metrics and logs"""
        try:
            # Get service details
            service_response = self.ecs.describe_services(
                cluster=cluster_name, services=[service_name]
            )

            if not service_response["services"]:
                return

            service = service_response["services"][0]

            # Get CPU and Memory metrics
            metrics = await self._get_service_metrics(cluster_name, service_name)

            # Get target group metrics if service is attached to ALB
            target_group_metrics = await self._get_target_group_metrics(
                cluster_name, service_name, service
            )
            if target_group_metrics:
                metrics["target_group"] = target_group_metrics

            # Store metrics for AI analysis
            await self._store_metrics(cluster_name, service_name, metrics)

        except Exception as e:
            logger.error(f"Error analyzing service {service_name}: {e}")

    async def _get_service_metrics(self, cluster_name: str, service_name: str) -> Dict:
        """Get CloudWatch metrics for service"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=self.timedelta_days)
        period = self.period

        metrics = {}

        # CPU Utilization
        try:
            logger.debug(f"Getting CPU metrics for {cluster_name}/{service_name}")
            cpu_response = self.cloudwatch.get_metric_statistics(
                Namespace=Config.ECS_NAMESPACE,
                MetricName=Config.CPU_METRIC_NAME,
                Dimensions=[
                    {"Name": "ServiceName", "Value": service_name},
                    {"Name": "ClusterName", "Value": cluster_name},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average", "Maximum"],
            )
            logger.debug(
                f"CPU response datapoints count: {len(cpu_response['Datapoints'])}"
            )
            # Convert datetime objects to ISO strings
            cpu_data = []
            for dp in cpu_response["Datapoints"]:
                cpu_data.append(
                    {
                        "Timestamp": dp["Timestamp"].isoformat(),
                        "Average": dp.get("Average", 0),
                        "Maximum": dp.get("Maximum", 0),
                        "Unit": dp.get("Unit", "Percent"),
                    }
                )
            metrics["cpu"] = cpu_data
        except Exception as e:
            logger.error(
                f"Error getting CPU metrics for {cluster_name}/{service_name}: {e}"
            )
            metrics["cpu"] = []

        # Memory Utilization
        try:
            logger.debug(f"Getting Memory metrics for {cluster_name}/{service_name}")
            memory_response = self.cloudwatch.get_metric_statistics(
                Namespace=Config.ECS_NAMESPACE,
                MetricName=Config.MEMORY_METRIC_NAME,
                Dimensions=[
                    {"Name": "ServiceName", "Value": service_name},
                    {"Name": "ClusterName", "Value": cluster_name},
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=["Average", "Maximum"],
            )
            logger.debug(
                f"Memory response datapoints count: {len(memory_response['Datapoints'])}"
            )
            # Convert datetime objects to ISO strings
            memory_data = []
            for dp in memory_response["Datapoints"]:
                memory_data.append(
                    {
                        "Timestamp": dp["Timestamp"].isoformat(),
                        "Average": dp.get("Average", 0),
                        "Maximum": dp.get("Maximum", 0),
                        "Unit": dp.get("Unit", "Percent"),
                    }
                )
            metrics["memory"] = memory_data
        except Exception as e:
            logger.error(
                f"Error getting memory metrics for {cluster_name}/{service_name}: {e}"
            )
            metrics["memory"] = []

        return metrics

    async def _get_target_group_metrics(
        self, cluster_name: str, service_name: str, service_info: Dict
    ) -> Dict:
        """Get target group metrics if service is attached to Application Load Balancer"""
        try:
            # Check if service has load balancers configured
            if not service_info.get("loadBalancers"):
                return {}

            target_group_metrics = {}

            for lb_config in service_info["loadBalancers"]:
                target_group_arn = lb_config.get("targetGroupArn")
                if not target_group_arn:
                    continue

                # Get target group details
                tg_response = self.elbv2.describe_target_groups(
                    TargetGroupArns=[target_group_arn]
                )

                if not tg_response["TargetGroups"]:
                    continue

                target_group = tg_response["TargetGroups"][0]

                # Get load balancer details to check if it's ALB
                lb_arn = (
                    target_group["LoadBalancerArns"][0]
                    if target_group.get("LoadBalancerArns")
                    else None
                )
                if not lb_arn:
                    continue

                lb_response = self.elbv2.describe_load_balancers(
                    LoadBalancerArns=[lb_arn]
                )

                if not lb_response["LoadBalancers"]:
                    continue

                load_balancer = lb_response["LoadBalancers"][0]

                # Skip if it's Network Load Balancer
                if load_balancer["Type"] != "application":
                    continue

                # Get target group name for CloudWatch metrics
                tg_name = target_group["TargetGroupName"]
                lb_name = load_balancer["LoadBalancerName"]

                # Get target group metrics - try recent data
                end_time = datetime.now()
                start_time = end_time - timedelta(days=self.timedelta_days)

                # Also try a longer period
                period = self.period

                # Extract proper dimension values
                # Target group ARN: arn:aws:elasticloadbalancing:region:account:targetgroup/name/id
                # Load balancer ARN: arn:aws:elasticloadbalancing:region:account:loadbalancer/app/name/id
                tg_full_name = target_group_arn.split(":")[-1]  # targetgroup/name/id
                lb_full_name = lb_arn.split("loadbalancer/")[
                    1
                ]  # loadbalancer/app/name/id

                # Healthy Host Count
                try:
                    healthy_hosts = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.HEALTHY_HOSTS_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Average", "Maximum"],
                    )

                except Exception as e:
                    healthy_hosts = {"Datapoints": []}

                # Unhealthy Host Count
                try:
                    unhealthy_hosts = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.UNHEALTHY_HOSTS_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Average", "Maximum"],
                    )

                except Exception as e:
                    unhealthy_hosts = {"Datapoints": []}

                # Target Response Time
                try:
                    response_time = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.TARGET_RESPONSE_TIME_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Average", "Maximum"],
                    )

                except Exception as e:
                    response_time = {"Datapoints": []}

                # Request Count
                try:
                    request_count = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.REQUEST_COUNT_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Sum"],
                    )

                except Exception as e:
                    request_count = {"Datapoints": []}

                # HTTP Status Code Metrics
                http_2xx = {"Datapoints": []}
                http_3xx = {"Datapoints": []}
                http_4xx = {"Datapoints": []}

                # HTTPCode_Target_2XX_Count
                try:
                    http_2xx = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.HTTP_2XX_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Sum"],
                    )
                except Exception as e:
                    pass

                # HTTPCode_Target_3XX_Count
                try:
                    http_3xx = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.HTTP_3XX_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Sum"],
                    )
                except Exception as e:
                    pass

                # HTTPCode_Target_4XX_Count
                try:
                    http_4xx = self.cloudwatch.get_metric_statistics(
                        Namespace=Config.ALB_NAMESPACE,
                        MetricName=Config.HTTP_4XX_METRIC,
                        Dimensions=[
                            {"Name": "TargetGroup", "Value": tg_full_name},
                            {"Name": "LoadBalancer", "Value": lb_full_name},
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        Period=period,
                        Statistics=["Sum"],
                    )
                except Exception as e:
                    pass

                # Calculate error percentage
                total_2xx = sum(dp.get("Sum", 0) for dp in http_2xx["Datapoints"])
                total_3xx = sum(dp.get("Sum", 0) for dp in http_3xx["Datapoints"])
                total_4xx = sum(dp.get("Sum", 0) for dp in http_4xx["Datapoints"])

                total_errors = total_3xx + total_4xx
                http_error_percentage = 0.0

                if total_2xx > 0:
                    http_error_percentage = round((total_errors / total_2xx) * 100, 2)
                elif total_errors > 0:
                    http_error_percentage = 100.0

                # Format metrics data
                target_group_metrics[tg_name] = {
                    "target_group_arn": target_group_arn,
                    "target_group_full_name": tg_full_name,
                    "load_balancer_name": lb_name,
                    "load_balancer_full_name": lb_full_name,
                    "load_balancer_type": load_balancer["Type"],
                    "healthy_hosts": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Average": dp.get("Average", 0),
                            "Maximum": dp.get("Maximum", 0),
                        }
                        for dp in healthy_hosts["Datapoints"]
                    ],
                    "unhealthy_hosts": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Average": dp.get("Average", 0),
                            "Maximum": dp.get("Maximum", 0),
                        }
                        for dp in unhealthy_hosts["Datapoints"]
                    ],
                    "response_time": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Average": dp.get("Average", 0),
                            "Maximum": dp.get("Maximum", 0),
                        }
                        for dp in response_time["Datapoints"]
                    ],
                    "request_count": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Sum": dp.get("Sum", 0),
                        }
                        for dp in request_count["Datapoints"]
                    ],
                    "http_2xx_count": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Sum": dp.get("Sum", 0),
                        }
                        for dp in http_2xx["Datapoints"]
                    ],
                    "http_3xx_count": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Sum": dp.get("Sum", 0),
                        }
                        for dp in http_3xx["Datapoints"]
                    ],
                    "http_4xx_count": [
                        {
                            "Timestamp": dp["Timestamp"].isoformat(),
                            "Sum": dp.get("Sum", 0),
                        }
                        for dp in http_4xx["Datapoints"]
                    ],
                    "http_error_percentage": http_error_percentage,
                    "total_2xx_count": total_2xx,
                    "total_3xx_count": total_3xx,
                    "total_4xx_count": total_4xx,
                }

            return target_group_metrics

        except Exception as e:
            logger.error(f"Error getting target group metrics for {service_name}: {e}")
            return {}

    async def _store_metrics(self, cluster_name: str, service_name: str, metrics: Dict):
        """Store metrics for later analysis"""
        # This would typically store in DynamoDB or similar
        pass

    async def get_status(self) -> Dict:
        """Get current monitoring status"""
        return {
            "status": "active" if self.clusters else "inactive",
            "clusters": self.clusters,
            "last_updated": self.last_updated or "never",
        }

    async def get_cluster_metrics(self) -> Dict:
        """Get aggregated cluster metrics"""
        metrics = {}
        for cluster in self.clusters:
            try:
                service_arns = self._get_all_services(cluster)
                cluster_metrics = []

                for service_arn in service_arns:
                    service_name = service_arn.split("/")[-1]
                    service_metrics = await self._get_service_metrics(
                        cluster, service_name
                    )

                    # Get service details for target group metrics
                    service_response = self.ecs.describe_services(
                        cluster=cluster, services=[service_name]
                    )

                    target_group_metrics = {}
                    if service_response["services"]:
                        service_info = service_response["services"][0]
                        target_group_metrics = await self._get_target_group_metrics(
                            cluster, service_name, service_info
                        )

                    cluster_metrics.append(
                        {
                            "service": service_name,
                            "metrics": service_metrics,
                            "target_group": target_group_metrics,
                        }
                    )

                metrics[cluster] = cluster_metrics
            except Exception as e:
                logger.error(f"Error getting metrics for cluster {cluster}: {e}")

        return metrics

    async def get_recent_logs(self) -> Dict:
        """Get recent logs from ECS services"""
        logs = {}
        for cluster in self.clusters:
            try:
                # Get log groups for ECS services
                log_groups_response = self.logs.describe_log_groups(
                    logGroupNamePrefix=f"/ecs/{cluster}"
                )

                cluster_logs = []
                for log_group in log_groups_response["logGroups"][
                    : Config.LOG_GROUPS_LIMIT
                ]:
                    try:
                        # Get log streams for this log group
                        streams_response = self.logs.describe_log_streams(
                            logGroupName=log_group["logGroupName"],
                            orderBy="LastEventTime",
                            descending=True,
                            limit=Config.LOG_STREAMS_LIMIT,
                        )

                        # Get events from each stream
                        for stream in streams_response["logStreams"]:
                            log_events = self.logs.get_log_events(
                                logGroupName=log_group["logGroupName"],
                                logStreamName=stream["logStreamName"],
                                startTime=int(
                                    (datetime.now() - timedelta(hours=1)).timestamp()
                                    * 1000
                                ),
                                limit=Config.LOG_EVENTS_LIMIT,
                            )
                            cluster_logs.extend(
                                [event["message"] for event in log_events["events"]]
                            )
                    except Exception as stream_error:
                        logger.error(
                            f"Error getting log streams for {log_group['logGroupName']}: {stream_error}"
                        )
                        continue

                logs[cluster] = cluster_logs[: Config.TOTAL_LOGS_LIMIT]
            except Exception as e:
                logger.error(f"Error getting logs for cluster {cluster}: {e}")
                logs[cluster] = []

        return logs

    async def get_cluster_details(self) -> Dict:
        """Get detailed cluster and service information"""
        details = {}
        for cluster in self.clusters:
            try:
                service_arns = self._get_all_services(cluster)
                services_details = []

                if service_arns:
                    # Process services in batches (AWS limit)
                    for i in range(0, len(service_arns), Config.ECS_BATCH_SIZE):
                        batch_arns = service_arns[i : i + Config.ECS_BATCH_SIZE]
                        services_info = self.ecs.describe_services(
                            cluster=cluster, services=batch_arns
                        )

                        for service in services_info["services"]:
                            service_name = service["serviceName"]
                            metrics = await self._get_service_metrics(
                                cluster, service_name
                            )

                            # Get target group metrics
                            target_group_metrics = await self._get_target_group_metrics(
                                cluster, service_name, service
                            )

                            # Get task definition details
                            task_definition_details = {}
                            task_definition_details = self.get_task_definition_details(
                                service, service_name
                            )

                            cpu_avg = 0
                            cpu_max = 0
                            memory_avg = 0
                            memory_max = 0
                            if metrics.get("cpu"):
                                cpu_avg = round(
                                    sum(dp["Average"] for dp in metrics["cpu"])
                                    / len(metrics["cpu"]),
                                    1,
                                )
                                cpu_max = round(
                                    max(dp["Maximum"] for dp in metrics["cpu"]), 1
                                )
                            if metrics.get("memory"):
                                memory_avg = round(
                                    sum(dp["Average"] for dp in metrics["memory"])
                                    / len(metrics["memory"]),
                                    1,
                                )
                                memory_max = round(
                                    max(dp["Maximum"] for dp in metrics["memory"]), 1
                                )

                            # Calculate target group averages
                            tg_summary = {}
                            if target_group_metrics:
                                for tg_name, tg_data in target_group_metrics.items():
                                    healthy_avg = (
                                        round(
                                            sum(
                                                dp["Average"]
                                                for dp in tg_data["healthy_hosts"]
                                            )
                                            / len(tg_data["healthy_hosts"]),
                                            1,
                                        )
                                        if tg_data["healthy_hosts"]
                                        else 0
                                    )
                                    healthy_max = (
                                        round(
                                            max(
                                                dp["Maximum"]
                                                for dp in tg_data["healthy_hosts"]
                                            ),
                                            1,
                                        )
                                        if tg_data["healthy_hosts"]
                                        else 0
                                    )
                                    unhealthy_avg = (
                                        round(
                                            sum(
                                                dp["Average"]
                                                for dp in tg_data["unhealthy_hosts"]
                                            )
                                            / len(tg_data["unhealthy_hosts"]),
                                            1,
                                        )
                                        if tg_data["unhealthy_hosts"]
                                        else 0
                                    )
                                    unhealthy_max = (
                                        round(
                                            max(
                                                dp["Maximum"]
                                                for dp in tg_data["unhealthy_hosts"]
                                            ),
                                            1,
                                        )
                                        if tg_data["unhealthy_hosts"]
                                        else 0
                                    )
                                    response_time_avg = (
                                        round(
                                            sum(
                                                dp["Average"]
                                                for dp in tg_data["response_time"]
                                            )
                                            / len(tg_data["response_time"]),
                                            3,
                                        )
                                        if tg_data["response_time"]
                                        else 0
                                    )
                                    response_time_max = (
                                        round(
                                            max(
                                                dp["Maximum"]
                                                for dp in tg_data["response_time"]
                                            ),
                                            3,
                                        )
                                        if tg_data["response_time"]
                                        else 0
                                    )
                                    request_avg = (
                                        round(
                                            sum(
                                                dp["Sum"]
                                                for dp in tg_data["request_count"]
                                            )
                                            / len(tg_data["request_count"]),
                                            1,
                                        )
                                        if tg_data["request_count"]
                                        else 0
                                    )
                                    request_max = (
                                        round(
                                            max(
                                                dp["Sum"]
                                                for dp in tg_data["request_count"]
                                            ),
                                            1,
                                        )
                                        if tg_data["request_count"]
                                        else 0
                                    )

                                    tg_summary[tg_name] = {
                                        "healthy_hosts_avg": healthy_avg,
                                        "healthy_hosts_max": healthy_max,
                                        "unhealthy_hosts_avg": unhealthy_avg,
                                        "unhealthy_hosts_max": unhealthy_max,
                                        "response_time_avg": response_time_avg,
                                        "response_time_max": response_time_max,
                                        "requests_avg": request_avg,
                                        "requests_max": request_max,
                                        "http_error_percentage": tg_data.get(
                                            "http_error_percentage", 0
                                        ),
                                        "total_2xx_count": tg_data.get(
                                            "total_2xx_count", 0
                                        ),
                                        "total_3xx_count": tg_data.get(
                                            "total_3xx_count", 0
                                        ),
                                        "total_4xx_count": tg_data.get(
                                            "total_4xx_count", 0
                                        ),
                                    }

                            services_details.append(
                                {
                                    "name": service_name,
                                    "status": service["status"],
                                    "running_count": service["runningCount"],
                                    "desired_count": service["desiredCount"],
                                    "cpu_avg": cpu_avg,
                                    "cpu_max": cpu_max,
                                    "memory_avg": memory_avg,
                                    "memory_max": memory_max,
                                    "target_groups": tg_summary,
                                    "task_definition": task_definition_details,
                                }
                            )

                details[cluster] = services_details
            except Exception as e:
                logger.error(f"Error getting cluster details for {cluster}: {e}")
                details[cluster] = []

        return details

    def get_task_definition_details(self, service, service_name):
        if service.get("taskDefinition"):
            try:
                task_def_response = self.ecs.describe_task_definition(
                    taskDefinition=service["taskDefinition"]
                )

                if task_def_response.get("taskDefinition"):
                    task_def = task_def_response["taskDefinition"]

                    # Extract container details
                    containers = []
                    for container in task_def.get("containerDefinitions", []):
                        containers.append(
                            {
                                "name": container.get("name"),
                                "cpu": container.get("cpu", 0),
                                "memory": container.get("memory"),
                                "memoryReservation": container.get("memoryReservation"),
                            }
                        )

                    task_definition_details = {
                        "family": task_def.get("family"),
                        "revision": task_def.get("revision"),
                        "compatibilities": task_def.get("compatibilities", []),
                        "requiresCompatibilities": task_def.get(
                            "requiresCompatibilities", []
                        ),
                        "cpu": task_def.get("cpu"),
                        "memory": task_def.get("memory"),
                        "containers": containers,
                    }
            except Exception as e:
                logger.error(f"Error getting task definition for {service_name}: {e}")
        return task_definition_details

    def get_scaling_policies(self, cluster_name: str, service_name: str) -> Dict:
        """Get Auto Scaling policies for ECS service"""
        try:
            resource_id = f"service/{cluster_name}/{service_name}"

            # Get scalable targets
            targets_response = self.autoscaling.describe_scalable_targets(
                ServiceNamespace="ecs", ResourceIds=[resource_id]
            )

            scaling_info = {}
            if targets_response["ScalableTargets"]:
                target = targets_response["ScalableTargets"][0]
                scaling_info = {
                    "min_capacity": target["MinCapacity"],
                    "max_capacity": target["MaxCapacity"],
                    "role_arn": target["RoleARN"],
                }

                # Get scaling policies
                policies_response = self.autoscaling.describe_scaling_policies(
                    ServiceNamespace="ecs", ResourceId=resource_id
                )

                policies = []
                for policy in policies_response["ScalingPolicies"]:
                    policy_info = {
                        "policy_name": policy["PolicyName"],
                        "policy_type": policy["PolicyType"],
                        "scalable_dimension": policy["ScalableDimension"],
                    }

                    if policy["PolicyType"] == "TargetTrackingScaling":
                        config = policy["TargetTrackingScalingPolicyConfiguration"]
                        policy_info["target_value"] = config["TargetValue"]
                        policy_info["metric_type"] = config.get(
                            "PredefinedMetricSpecification", {}
                        ).get("PredefinedMetricType")
                    elif policy["PolicyType"] == "StepScaling":
                        config = policy["StepScalingPolicyConfiguration"]
                        policy_info["adjustment_type"] = config["AdjustmentType"]
                        policy_info["cooldown"] = config.get("Cooldown")
                        policy_info["metric_aggregation_type"] = config.get(
                            "MetricAggregationType"
                        )
                        policy_info["step_adjustments"] = [
                            {
                                "metric_interval_lower_bound": step.get(
                                    "MetricIntervalLowerBound"
                                ),
                                "metric_interval_upper_bound": step.get(
                                    "MetricIntervalUpperBound"
                                ),
                                "scaling_adjustment": step["ScalingAdjustment"],
                            }
                            for step in config.get("StepAdjustments", [])
                        ]

                    policies.append(policy_info)

                scaling_info["policies"] = policies

            return scaling_info

        except Exception as e:
            logger.error(f"Error getting scaling policies for {service_name}: {e}")
            return {}

    async def get_service_specific_metrics(
        self, cluster_name: str, service_name: str
    ) -> Dict:
        """Get specific metrics for a service including target group metrics"""
        metrics = await self._get_service_metrics(cluster_name, service_name)

        # Get service details for target group metrics
        try:
            service_response = self.ecs.describe_services(
                cluster=cluster_name, services=[service_name]
            )

            if service_response["services"]:
                service_info = service_response["services"][0]

                # Add service counts
                metrics["running_count"] = service_info["runningCount"]
                metrics["desired_count"] = service_info["desiredCount"]

                # Get task definition details
                metrics["task_definition"] = self.get_task_definition_details(
                    service_info, service_name
                )

                # Get scaling policies
                metrics["scaling_policies"] = self.get_scaling_policies(
                    cluster_name, service_name
                )

                # Get target group metrics
                target_group_metrics = await self._get_target_group_metrics(
                    cluster_name, service_name, service_info
                )
                if target_group_metrics:
                    metrics["target_group"] = target_group_metrics
        except Exception as e:
            logger.error(f"Error getting service info for target group metrics: {e}")

        return metrics

    async def get_service_logs(self, cluster_name: str, service_name: str) -> List[str]:
        """Get logs for a specific service"""
        try:
            log_groups_response = self.logs.describe_log_groups(
                logGroupNamePrefix=f"/ecs/{cluster_name}"
            )

            service_logs = []
            for log_group in log_groups_response["logGroups"]:
                if service_name in log_group["logGroupName"]:
                    try:
                        streams_response = self.logs.describe_log_streams(
                            logGroupName=log_group["logGroupName"],
                            orderBy="LastEventTime",
                            descending=True,
                            limit=1,
                        )

                        if streams_response["logStreams"]:
                            log_events = self.logs.get_log_events(
                                logGroupName=log_group["logGroupName"],
                                logStreamName=streams_response["logStreams"][0][
                                    "logStreamName"
                                ],
                                limit=Config.LOG_EVENTS_LIMIT,
                            )
                            service_logs.extend(
                                [event["message"] for event in log_events["events"]]
                            )
                    except:
                        continue

            return service_logs[: Config.TOTAL_LOGS_LIMIT]
        except Exception as e:
            logger.error(f"Error getting service logs: {e}")
            return []
