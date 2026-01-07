import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

import boto3

from config import Config
from logger_config import setup_logger

logger = setup_logger(__name__)


class KnowledgeDB:
    def __init__(self, region: str = Config.AWS_DEFAULT_REGION):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table_name = Config.KNOWLEDGE_TABLE_NAME
        self.recommendations_table_name = Config.RECOMMENDATIONS_TABLE_NAME
        self.table = None
        self.recommendations_table = None
        self._ensure_table()
        self._ensure_recommendations_table()

    def _ensure_table(self):
        """Ensure DynamoDB table exists"""
        try:
            self.table = self.dynamodb.Table(self.table_name)
            self.table.load()
        except:
            # Table doesn't exist, create it
            try:
                self.table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {"AttributeName": "pk", "KeyType": "HASH"},
                        {"AttributeName": "sk", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "pk", "AttributeType": "S"},
                        {"AttributeName": "sk", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                self.table.wait_until_exists()
            except Exception as e:
                logger.error(f"Error creating DynamoDB table: {e}")
                self.table = None

    def _ensure_recommendations_table(self):
        """Ensure service recommendations DynamoDB table exists"""
        try:
            self.recommendations_table = self.dynamodb.Table(
                self.recommendations_table_name
            )
            self.recommendations_table.load()
        except:
            # Table doesn't exist, create it
            try:
                self.recommendations_table = self.dynamodb.create_table(
                    TableName=self.recommendations_table_name,
                    KeySchema=[
                        {"AttributeName": "account_id", "KeyType": "HASH"},
                        {"AttributeName": "service_cluster_key", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "account_id", "AttributeType": "S"},
                        {"AttributeName": "service_cluster_key", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                self.recommendations_table.wait_until_exists()
            except Exception as e:
                logger.error(
                    f"Error creating service recommendations DynamoDB table: {e}"
                )
                self.recommendations_table = None

    async def store_recommendations(self, account_id: str, recommendations: Dict):
        """Store AI recommendations in knowledge database (single per account)"""
        if not self.table:
            return

        try:
            item = {
                "pk": f"ACCOUNT#{account_id}",
                "sk": "RECOMMENDATIONS",
                "account_id": account_id,
                "timestamp": datetime.now().isoformat(),
                "recommendations": json.dumps(recommendations),
                "ttl": int((datetime.now().timestamp() + Config.RECOMMENDATIONS_TTL)),
            }

            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing recommendations: {e}")

    async def store_metrics(
        self, account_id: str, cluster: str, service: str, metrics: Dict
    ):
        """Store service metrics"""
        if not self.table:
            return

        try:
            item = {
                "pk": f"ACCOUNT#{account_id}",
                "sk": f"METRICS#{cluster}#{service}#{datetime.now().isoformat()}",
                "account_id": account_id,
                "cluster": cluster,
                "service": service,
                "timestamp": datetime.now().isoformat(),
                "metrics": json.dumps(metrics),
                "ttl": int((datetime.now().timestamp() + Config.METRICS_TTL)),
            }

            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing metrics: {e}")

    async def get_current_recommendations(self, account_id: str) -> Dict:
        """Get current recommendations for account"""
        if not self.table:
            return {}

        try:
            response = self.table.get_item(
                Key={"pk": f"ACCOUNT#{account_id}", "sk": "RECOMMENDATIONS"}
            )

            if "Item" in response:
                rec = json.loads(response["Item"]["recommendations"])
                rec["stored_at"] = response["Item"]["timestamp"]
                return rec

            return {}
        except Exception as e:
            logger.error(f"Error getting current recommendations: {e}")
            return {}

    async def get_service_trends(
        self, account_id: str, cluster: str, service: str, days: int = 7
    ) -> Dict:
        """Get service performance trends"""
        if not self.table:
            return {}

        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date.replace(day=end_date.day - days)

            response = self.table.query(
                KeyConditionExpression="pk = :pk AND sk BETWEEN :start AND :end",
                ExpressionAttributeValues={
                    ":pk": f"ACCOUNT#{account_id}",
                    ":start": f"METRICS#{cluster}#{service}#{start_date.isoformat()}",
                    ":end": f"METRICS#{cluster}#{service}#{end_date.isoformat()}",
                },
            )

            trends = {
                "cpu_trend": [],
                "memory_trend": [],
                "data_points": len(response["Items"]),
            }

            for item in response["Items"]:
                metrics = json.loads(item["metrics"])

                # Extract CPU trend
                if metrics.get("cpu"):
                    avg_cpu = sum(dp["Average"] for dp in metrics["cpu"]) / len(
                        metrics["cpu"]
                    )
                    trends["cpu_trend"].append(
                        {"timestamp": item["timestamp"], "value": avg_cpu}
                    )

                # Extract Memory trend
                if metrics.get("memory"):
                    avg_memory = sum(dp["Average"] for dp in metrics["memory"]) / len(
                        metrics["memory"]
                    )
                    trends["memory_trend"].append(
                        {"timestamp": item["timestamp"], "value": avg_memory}
                    )

            return trends
        except Exception as e:
            logger.error(f"Error getting service trends: {e}")
            return {}

    async def store_learning_data(self, account_id: str, learning_data: Dict):
        """Store learning data for AI model improvement"""
        if not self.table:
            return

        try:
            item = {
                "pk": f"ACCOUNT#{account_id}",
                "sk": f"LEARNING#{uuid.uuid4()}",
                "account_id": account_id,
                "timestamp": datetime.now().isoformat(),
                "learning_data": json.dumps(learning_data),
                "ttl": int((datetime.now().timestamp() + Config.LEARNING_DATA_TTL)),
            }

            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing learning data: {e}")

    async def store_account(self, account_data: Dict):
        """Store account credentials and details"""
        if not self.table:
            return

        try:
            item = {
                "pk": f'ACCOUNT#{account_data["account_id"]}',
                "sk": "ACCOUNT_DATA",
                "account_id": account_data["account_id"],
                "account_name": account_data["account_name"],
                "access_key": account_data.get("access_key", ""),
                "secret_key": account_data.get("secret_key", ""),
                "profile_name": account_data.get("profile_name", ""),
                "role_arn": account_data.get("role_arn", ""),
                "session_token": account_data.get("session_token", ""),
                "region": account_data["region"],
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
            }

            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing account: {e}")

    async def get_all_accounts(self) -> List[Dict]:
        """Get all stored accounts"""
        if not self.table:
            return []

        try:
            response = self.table.scan(
                FilterExpression="sk = :sk",
                ExpressionAttributeValues={":sk": "ACCOUNT_DATA"},
            )

            accounts = []
            for item in response["Items"]:
                accounts.append(
                    {
                        "account_id": item["account_id"],
                        "account_name": item["account_name"],
                        "access_key": item.get("access_key", ""),
                        "secret_key": item.get("secret_key", ""),
                        "profile_name": item.get("profile_name", ""),
                        "role_arn": item.get("role_arn", ""),
                        "session_token": item.get("session_token", ""),
                        "region": item["region"],
                        "created_at": item["created_at"],
                        "last_updated": item["last_updated"],
                    }
                )

            return accounts
        except Exception as e:
            logger.error(f"Error getting accounts: {e}")
            return []

    async def store_cluster_data(self, account_id: str, cluster_data: Dict):
        """Store cluster and service data"""
        if not self.table:
            return

        try:
            item = {
                "pk": f"ACCOUNT#{account_id}",
                "sk": "CLUSTER_DATA",
                "account_id": account_id,
                "cluster_data": json.dumps(cluster_data),
                "timestamp": datetime.now().isoformat(),
                "ttl": int((datetime.now().timestamp() + Config.CLUSTER_DATA_TTL)),
            }

            self.table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing cluster data: {e}")

    async def get_cluster_data(self, account_id: str) -> Dict:
        """Get stored cluster data"""
        if not self.table:
            return {}

        try:
            response = self.table.get_item(
                Key={"pk": f"ACCOUNT#{account_id}", "sk": "CLUSTER_DATA"}
            )

            if "Item" in response:
                return json.loads(response["Item"]["cluster_data"])

            return {}
        except Exception as e:
            logger.error(f"Error getting cluster data: {e}")
            return {}

    async def store_service_recommendation(
        self, account_id: str, cluster: str, service: str, recommendation: Dict
    ):
        """Store service-specific recommendation in the new table"""
        if not self.recommendations_table:
            return

        try:
            item = {
                "account_id": account_id,
                "service_cluster_key": f"{cluster}#{service}",
                "service": service,
                "cluster": cluster,
                "service_health": recommendation.get("service_health", "unknown"),
                "scaling_action": recommendation.get("scaling_action", "no_change"),
                "priority": recommendation.get("priority", "medium"),
                "recommendations": json.dumps(recommendation),
                "timestamp": datetime.now().isoformat(),
                "ttl": int((datetime.now().timestamp() + Config.METRICS_TTL)),
            }

            self.recommendations_table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Error storing service recommendation: {e}")

    async def get_service_recommendations_by_health(
        self, account_id: str, health_status: str = None, priority: str = None
    ) -> List[Dict]:
        """Get service recommendations filtered by health status and/or priority"""
        if not self.recommendations_table:
            return []

        try:
            filter_expressions = []
            expression_values = {":account_id": account_id}

            if health_status:
                filter_expressions.append("service_health = :health")
                expression_values[":health"] = health_status

            if priority:
                filter_expressions.append("priority = :priority")
                expression_values[":priority"] = priority

            if filter_expressions:
                response = self.recommendations_table.query(
                    KeyConditionExpression="account_id = :account_id",
                    FilterExpression=" AND ".join(filter_expressions),
                    ExpressionAttributeValues=expression_values,
                )
            else:
                response = self.recommendations_table.query(
                    KeyConditionExpression="account_id = :account_id",
                    ExpressionAttributeValues=expression_values,
                )

            recommendations = []
            for item in response["Items"]:
                rec_data = json.loads(item["recommendations"])
                recommendations.append(
                    {
                        "account_id": item["account_id"],
                        "service": item["service"],
                        "cluster": item["cluster"],
                        "service_health": item["service_health"],
                        "scaling_action": item["scaling_action"],
                        "priority": item["priority"],
                        "timestamp": item["timestamp"],
                        "full_recommendation": rec_data,
                    }
                )

            return recommendations
        except Exception as e:
            logger.error(f"Error getting service recommendations: {e}")
            return []

    async def get_cluster_data_with_recommendations(self, account_id: str) -> Dict:
        """Get cluster data and generate service recommendations for each service"""
        cluster_data = await self.get_cluster_data(account_id)
        if not cluster_data:
            return {}

        # This method will be called by the new API endpoint
        # The actual recommendation generation will happen in the API endpoint
        return cluster_data

    async def get_knowledge_base_summary(self, account_id: str) -> Dict:
        """Get summary of stored knowledge for the account"""
        if not self.table:
            return {"error": "Knowledge database not available"}

        try:
            # Get counts of different data types
            response = self.table.query(
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": f"ACCOUNT#{account_id}"},
                Select="COUNT",
            )

            return {
                "account_id": account_id,
                "total_records": response["Count"],
                "last_updated": datetime.now().isoformat(),
                "status": "active",
            }
        except Exception as e:
            logger.error(f"Error getting knowledge base summary: {e}")
            return {"error": str(e)}
