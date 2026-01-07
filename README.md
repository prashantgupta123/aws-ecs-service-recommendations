# Building an AI-Powered ECS Monitoring System: From Chaos to Clarity

## Introduction

Managing containerized infrastructure at scale is challenging. When you're running dozens of ECS services across multiple AWS accounts, answering simple questions becomes surprisingly difficult: *Which services need scaling? Are we over-provisioned? What's causing that spike in response time?*

This article walks through building a production-ready ECS monitoring system that combines real-time metrics collection with AI-powered recommendations using AWS Bedrock's Claude Sonnet 4. We'll explore the architecture, implementation challenges, and lessons learned from processing thousands of container metrics daily.

**What You'll Learn:**
- Multi-account ECS monitoring architecture
- Integrating AWS Bedrock for intelligent recommendations
- Handling CloudWatch metrics at scale
- Building responsive dashboards with real-time data
- Implementing automated reporting workflows

## System Screenshots

### Analytics Dashboard
![Analytics Dashboard](screenshots/2-ECSAnalyticsDashboard.png)
*Comprehensive overview with real-time metrics, health distribution, and priority breakdown*

![Analytics Graphs](screenshots/3-ECSAnalyticsDashboard-Graphs.png)
*Interactive charts showing service health, scaling actions, and priority levels*

### Service Monitoring
![Service Metrics](screenshots/4-ECSServiceMetrics.png)
*Detailed service metrics including CPU, memory, task counts, and target group health*

### AI-Powered Recommendations
![Service Recommendations](screenshots/5-ECSServiceRecommendations.png)
*AI-generated recommendations with health status, scaling actions, and priority levels*

![Recommendations by Priority](screenshots/7-ECSServiceRecommendationsGroupByPriority.png)
*Recommendations organized by priority (High → Medium → Low) for focused attention*

### Interactive AI Chat
![Chat with AI](screenshots/6-ECSServiceRecommendationsChatWithAI.png)
*Ask questions about your infrastructure and get context-aware responses*

![AI Response](screenshots/6-ECSServiceRecommendationsChatWithAIReply.png)
*Detailed AI analysis with actionable insights and technical guidance*

### Account Management
![Account Onboarding](screenshots/9-AWSAccountOnBoardDashboard.png)
*Easy account onboarding with multiple authentication methods*

### API Documentation
![API Docs](screenshots/11-APIDocs.png)
*Comprehensive OpenAPI/Swagger documentation for all endpoints*

## The Problem Statement

### The Challenge

Modern cloud infrastructure teams face several pain points:

1. **Visibility Gap**: CloudWatch provides raw metrics, but interpreting them requires expertise
2. **Multi-Account Complexity**: Managing services across multiple AWS accounts is operationally expensive
3. **Reactive Operations**: Teams discover issues after they impact users
4. **Manual Analysis**: Engineers spend hours analyzing metrics to make scaling decisions
5. **Context Loss**: Metrics alone don't explain *why* a service is struggling

### Real-World Scenario

Consider a typical scenario: Your API service shows 85% CPU utilization. Is this a problem? It depends:
- What's the memory usage?
- Are response times degrading?
- Is the load balancer showing unhealthy targets?
- What do the application logs indicate?
- Is this a traffic spike or a memory leak?

Answering these questions requires correlating data from ECS, CloudWatch, ALB, and application logs—a time-consuming manual process.

### Our Solution

We built a system that:
- **Monitors** ECS services across multiple accounts automatically
- **Collects** comprehensive metrics (CPU, memory, ALB health, response times, HTTP status codes)
- **Analyzes** patterns using AI to provide actionable recommendations
- **Alerts** teams proactively with prioritized actions
- **Learns** from historical data to improve recommendations


## Architecture & Design Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Dashboard                             │
│  (Analytics, Services, Recommendations, Cluster Analysis)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Account    │  │     ECS      │  │      AI      │          │
│  │  Management  │  │   Monitor    │  │  Recommender │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└────────┬────────────────┬────────────────┬────────────────┬─────┘
         │                │                │                │
         ▼                ▼                ▼                ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐
│  DynamoDB    │  │     ECS      │  │   Bedrock    │  │   SES    │
│  (Knowledge  │  │  CloudWatch  │  │  (Claude 4)  │  │ (Email)  │
│   Database)  │  │     ALB      │  │              │  │          │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────┘
```

### Core Components

#### 1. **ECS Monitor** (`ecs_monitor.py`)
The monitoring engine that discovers and tracks ECS infrastructure:

- **Cluster Discovery**: Automatically finds all ECS clusters using pagination
- **Service Enumeration**: Lists services within each cluster (handles >100 services)
- **Metrics Collection**: Fetches CPU, memory, task counts from CloudWatch
- **ALB Integration**: Collects target group health, response times, HTTP status codes
- **Task Definition Analysis**: Extracts CPU/memory allocations at container level

**Key Design Decision**: We create monitor instances at runtime rather than storing them globally. This prevents session token expiration issues when using cross-account IAM roles.

#### 2. **AI Recommender** (`ai_recommender.py`)
Intelligent analysis engine powered by AWS Bedrock:

- **Metrics Summarization**: Aggregates raw metrics into actionable insights
- **Log Analysis**: Scans CloudWatch logs for error patterns
- **Prompt Engineering**: Crafts context-rich prompts for Claude Sonnet 4
- **Recommendation Parsing**: Structures AI responses into categorized actions
- **Fallback Logic**: Provides rule-based recommendations if AI is unavailable

**Model Choice**: We use Claude Sonnet 4 for its superior reasoning about infrastructure patterns and ability to provide nuanced recommendations.

#### 3. **Knowledge Database** (`knowledge_db.py`)
Persistent storage layer using DynamoDB:

- **Account Storage**: Stores credentials and configuration for multiple AWS accounts
- **Cluster Data Cache**: Caches service metrics (24-hour TTL)
- **Service Recommendations**: Individual service analysis with health status
- **Historical Tracking**: Maintains recommendation history for trend analysis

**Schema Design**:
```python
# Account Table
{
  "account_id": "123456789012",  # Hash Key
  "account_name": "production",
  "region": "us-east-1",
  "credentials": {...},
  "last_updated": "2024-01-15T10:30:00Z"
}

# Service Recommendation Table
{
  "account_id": "123456789012",  # Hash Key
  "service_cluster_key": "prod-cluster#api-service",  # Range Key
  "service_health": "warning",  # good|warning|critical|error
  "scaling_action": "scale_up",  # scale_up|scale_down|no_change
  "priority": "high",  # high|medium|low
  "recommendations": [...],
  "ttl": 1705324800  # Auto-delete after 7 days
}
```

#### 4. **FastAPI Application** (`app.py`)
RESTful API and web server:

- **Authentication**: Cognito JWT validation (optional for local dev)
- **Rate Limiting**: 100 req/min for reads, 10 req/min for writes
- **Async Processing**: Parallel service analysis using asyncio
- **Scheduled Jobs**: Daily/weekly cron jobs for automated reports
- **WebSocket Support**: Real-time dashboard updates

### Data Flow

#### Service Discovery Flow
```
1. User adds AWS account → Store credentials in DynamoDB
2. ECS Monitor created → Discover clusters (with pagination)
3. For each cluster → List services (batch processing)
4. For each service → Collect metrics (parallel execution)
5. Store in cache → DynamoDB with 24h TTL
```

#### Recommendation Generation Flow
```
1. API call triggers analysis → Get cached cluster data
2. For each service → Fetch CloudWatch metrics (7-day window)
3. Collect ALB metrics → Target group health, response times
4. Aggregate data → Summarize CPU, memory, traffic patterns
5. Call Bedrock API → Send structured prompt to Claude
6. Parse AI response → Extract scaling actions, priorities
7. Store recommendations → DynamoDB with service health status
8. Return to dashboard → Display with priority grouping
```

### Scalability Considerations

**Pagination Handling**: AWS APIs limit results (100 clusters, 10 services per call). We implement pagination loops to handle large accounts.

**Batch Processing**: ECS `describe_services` accepts max 10 services. We batch requests to avoid API limits.

**Parallel Execution**: Service analysis runs concurrently using `asyncio.gather()` to reduce latency.

**Caching Strategy**: Cluster data cached for 24 hours to minimize CloudWatch API calls and costs.

**Session Management**: Fresh boto3 sessions created per request to handle temporary credentials and cross-account roles.


## Solution Approach

### Design Principles

1. **Multi-Tenancy First**: Support multiple AWS accounts with different authentication methods
2. **AI-Augmented, Not AI-Dependent**: Provide fallback recommendations if Bedrock is unavailable
3. **Service-Level Granularity**: Analyze each service individually rather than cluster-wide averages
4. **Priority-Based Actions**: Categorize recommendations (high/medium/low) for focused attention
5. **Historical Context**: Store recommendations to track service health trends over time

### Authentication Strategy

We support five authentication methods to accommodate different deployment scenarios:

```python
# 1. IAM Role (Production - Most Secure)
# No credentials needed, uses EC2/ECS instance profile

# 2. AWS Profile (Local Development)
profile_name = "production-readonly"

# 3. Cross-Account Role (Multi-Account)
role_arn = "arn:aws:iam::123456789012:role/ECSMonitoringRole"
external_id = "ecs-monitoring-app"

# 4. Access Keys (CI/CD)
access_key = os.getenv("AWS_ACCESS_KEY_ID")
secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

# 5. Session Token (Temporary Credentials)
session_token = os.getenv("AWS_SESSION_TOKEN")
```

**Implementation** (`AWSSession.py`):
```python
def get_aws_session(region, profile_name, role_arn, access_key, secret_key, session_token):
    if role_arn:
        # Assume cross-account role with 4-hour session
        sts = boto3.client('sts')
        assumed_role = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ecs-monitoring',
            ExternalId='ecs-monitoring-app',
            DurationSeconds=14400  # 4 hours
        )
        return boto3.Session(
            aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
            aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
            aws_session_token=assumed_role['Credentials']['SessionToken'],
            region_name=region
        )
    elif profile_name:
        return boto3.Session(profile_name=profile_name, region_name=region)
    elif access_key and secret_key:
        return boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            aws_session_token=session_token,
            region_name=region
        )
    else:
        # Use default credentials (environment, instance profile)
        return boto3.Session(region_name=region)
```

### Metrics Collection Strategy

#### CloudWatch Metrics
We collect 7 days of metrics with 1-hour granularity:

```python
end_time = datetime.now()
start_time = end_time - timedelta(days=7)
period = 3600  # 1 hour

# CPU Utilization
cpu_response = cloudwatch.get_metric_statistics(
    Namespace='AWS/ECS',
    MetricName='CPUUtilization',
    Dimensions=[
        {'Name': 'ServiceName', 'Value': service_name},
        {'Name': 'ClusterName', 'Value': cluster_name}
    ],
    StartTime=start_time,
    EndTime=end_time,
    Period=period,
    Statistics=['Average', 'Maximum']
)
```

#### ALB Target Group Metrics
For services behind Application Load Balancers:

```python
# Extract proper dimension values from ARNs
tg_full_name = target_group_arn.split(':')[-1]  # targetgroup/name/id
lb_full_name = lb_arn.split('loadbalancer/')[1]  # app/name/id

# Healthy/Unhealthy host counts
# Response time (average and maximum)
# Request volume
# HTTP status codes (2XX, 3XX, 4XX)

# Calculate error percentage
error_percentage = ((total_3xx + total_4xx) / total_2xx) * 100
```

**Why ALB Only?** Network Load Balancers don't expose target-level health metrics in CloudWatch, so we skip NLB-attached services.

### AI Prompt Engineering

The quality of recommendations depends heavily on prompt structure. Here's our approach:

```python
prompt = f"""
You are an AWS ECS infrastructure expert. Analyze the following data:

METRICS SUMMARY:
- Cluster: prod-cluster
- Services: 12
- High CPU services: api-service (avg: 85%, max: 92%)
- High memory services: worker-service (avg: 78%, max: 88%)
- High response time: api-service (avg: 1.2s, max: 3.5s)
- Unhealthy targets: api-service (2 unhealthy hosts)

LOG ANALYSIS:
- Total logs: 1,500
- Error count: 45 (3% error rate)
- Common errors: OutOfMemory (12), ConnectionTimeout (8)

Provide recommendations in JSON format:
{{
  "overall_health": "warning",
  "scaling_recommendations": [
    {{
      "cluster": "prod-cluster",
      "service": "api-service",
      "action": "scale_up",
      "reason": "High CPU (85%) with degraded response times",
      "suggested_capacity": {{
        "desired_count": 5,
        "cpu": 1024,
        "memory": 2048
      }}
    }}
  ],
  "performance_issues": [...],
  "cost_optimization": [...],
  "summary": "Overall assessment"
}}

Focus on:
1. Services with CPU > 80% or Memory > 80% need scaling
2. High error rates indicate application issues
3. Provide specific, actionable recommendations
"""
```

**Key Techniques**:
- **Structured Output**: Request JSON format for easy parsing
- **Context-Rich**: Include metrics, logs, and historical patterns
- **Specific Thresholds**: Define what "high" means (80% CPU)
- **Actionable Focus**: Ask for specific capacity numbers, not vague suggestions

## Code Walkthrough

### 1. Service Discovery with Pagination

AWS limits API responses (100 clusters, 10 services). We handle this with pagination:

```python
def _get_all_clusters(self) -> List[str]:
    """Get all clusters with pagination"""
    cluster_arns = []
    next_token = None

    while True:
        params = {}
        if next_token:
            params['nextToken'] = next_token

        response = self.ecs.list_clusters(**params)
        cluster_arns.extend(response.get('clusterArns', []))

        next_token = response.get('nextToken')
        if not next_token:
            break

    return cluster_arns
```

### 2. Parallel Service Analysis

Analyzing services sequentially is slow. We use asyncio for parallelism:

```python
async def get_cluster_recommendations(account_id: str):
    cluster_data = await knowledge_db.get_cluster_data(account_id)

    async def process_service(cluster_name, service):
        # Get metrics
        service_metrics = await monitor.get_service_specific_metrics(
            cluster_name, service['name']
        )

        # Generate AI recommendations
        recommendation = await generate_service_recommendations(
            bedrock_client, model_id, service_metrics,
            service_logs, cluster_name, service['name']
        )

        # Store in database
        await knowledge_db.store_service_recommendation(
            account_id, cluster_name, service['name'], recommendation
        )

        return recommendation

    # Process all services in parallel
    for cluster_name, services in cluster_data.items():
        results = await asyncio.gather(
            *[process_service(cluster_name, service) for service in services]
        )
```

**Performance Impact**: Analyzing 50 services takes ~30 seconds with parallelism vs. ~5 minutes sequentially.

### 3. Batch Processing for ECS API

AWS ECS `describe_services` accepts maximum 10 services per call:

```python
# Process services in batches
for i in range(0, len(service_arns), 10):
    batch_arns = service_arns[i:i+10]
    services_info = self.ecs.describe_services(
        cluster=cluster,
        services=batch_arns
    )
    # Process batch...
```

### 4. AI Recommendation Parsing

Claude's responses need robust parsing:

```python
def _parse_recommendations(self, ai_response: str, data: Dict) -> Dict:
    try:
        # Extract JSON from response
        start_idx = ai_response.find('{')
        end_idx = ai_response.rfind('}') + 1

        if start_idx != -1 and end_idx != -1:
            json_str = ai_response[start_idx:end_idx]
            recommendations = json.loads(json_str)
            recommendations['generated_at'] = data['timestamp']
            return recommendations
    except Exception as e:
        logger.error(f"JSON parsing failed: {e}")

    # Fallback to rule-based recommendations
    return self._fallback_recommendations(data)
```

**Why Fallback?** AI services can fail or return malformed JSON. We provide rule-based recommendations as a safety net.

### 5. Scheduled Cron Jobs

Automated daily and weekly reports using APScheduler:

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

# Daily: Generate recommendations at 7 AM
scheduler.add_job(
    generate_daily_cluster_recommendations,
    CronTrigger(hour=7, minute=0),
    id='daily_cluster_recommendations'
)

# Daily: Send high-priority reports at 9 AM
scheduler.add_job(
    send_daily_high_priority_reports,
    CronTrigger(hour=9, minute=0),
    id='daily_high_priority_reports'
)

# Weekly: Comprehensive reports on Monday at 10 AM
scheduler.add_job(
    send_weekly_comprehensive_reports,
    CronTrigger(day_of_week='mon', hour=10, minute=0),
    id='weekly_comprehensive_reports'
)

scheduler.start()
```

### 6. DynamoDB TTL for Auto-Cleanup

Recommendations expire after 7 days automatically:

```python
await dynamodb.put_item(
    TableName='ecs-service-recommendation',
    Item={
        'account_id': account_id,
        'service_cluster_key': f"{cluster}#{service}",
        'recommendations': recommendation,
        'timestamp': datetime.now().isoformat(),
        'ttl': int((datetime.now() + timedelta(days=7)).timestamp())
    }
)
```

DynamoDB automatically deletes items when TTL expires, keeping storage costs low.


## Configuration & Setup

### Prerequisites

- **Python 3.13+** (uses modern async features)
- **AWS Account** with ECS services
- **Bedrock Access** (Claude Sonnet 4 model enabled in your region)
- **Docker** (optional, for containerized deployment)

### Environment Variables

Create a `.env` file with the following configuration:

```bash
# AWS Configuration
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key_here  # Optional if using IAM roles
AWS_SECRET_ACCESS_KEY=your_secret_here

# Bedrock AI Model
BEDROCK_MODEL_NAME=apac.anthropic.claude-3-7-sonnet-20250219-v1:0

# Authentication (Optional - for local development)
DISABLE_AUTH=true  # Set to false in production

# Cognito (Required when DISABLE_AUTH=false)
COGNITO_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=your_client_id_here

# Email Notifications (AWS SES)
EMAIL_SOURCE=no-reply@yourdomain.com
EMAIL_DESTINATION=team@yourdomain.com,ops@yourdomain.com
EMAIL_CC=manager@yourdomain.com

# Cron Job Configuration
DAILY_RECOMMENDATIONS_CRON_ENABLED=true
WEEKLY_RECOMMENDATIONS_CRON_ENABLED=true

# Application Settings
LOG_LEVEL=INFO
PORT=8000
```

### IAM Permissions

The application requires specific IAM permissions. Create a policy using the provided `iam-policies.json`:

```bash
# Create IAM policy
aws iam create-policy \
  --policy-name ECSMonitoringPolicy \
  --policy-document file://iam-policies.json

# Attach to your IAM role
aws iam attach-role-policy \
  --role-name YourApplicationRole \
  --policy-arn arn:aws:iam::ACCOUNT_ID:policy/ECSMonitoringPolicy
```

**Required Permissions**:
- `ecs:ListClusters`, `ecs:ListServices`, `ecs:DescribeServices`
- `ecs:DescribeTaskDefinition` (for container resource analysis)
- `cloudwatch:GetMetricStatistics` (for CPU, memory, ALB metrics)
- `logs:DescribeLogGroups`, `logs:DescribeLogStreams`, `logs:GetLogEvents`
- `elasticloadbalancing:DescribeTargetGroups`, `DescribeLoadBalancers`
- `bedrock:InvokeModel` (for AI recommendations)
- `dynamodb:PutItem`, `GetItem`, `Query`, `Scan` (for knowledge database)
- `ses:SendEmail` (for email notifications)

### Installation

#### Option 1: Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/aws-ecs-service-recommendations.git
cd aws-ecs-service-recommendations

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Run application
python app.py
```

#### Option 2: Docker Deployment

```bash
# Build Docker image
docker build -t ecs-monitoring .

# Run with environment file
docker run -p 8000:8000 --env-file .env ecs-monitoring

# Or use docker-compose
docker-compose up -d
```

#### Option 3: Production Deployment (ECS/Fargate)

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.us-east-1.amazonaws.com

docker build -t ecs-monitoring .
docker tag ecs-monitoring:latest ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ecs-monitoring:latest
docker push ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/ecs-monitoring:latest

# Deploy to ECS using task definition
aws ecs update-service \
  --cluster monitoring-cluster \
  --service ecs-monitoring-service \
  --force-new-deployment
```

### DynamoDB Table Setup

The application automatically creates required tables on first run:

**Table 1: `ecs-monitoring-knowledge`** (Account and cluster data)
- Hash Key: `account_id` (String)
- Range Key: `data_type` (String)
- TTL: `ttl` (Number)

**Table 2: `ecs-service-recommendation`** (Service-level recommendations)
- Hash Key: `account_id` (String)
- Range Key: `service_cluster_key` (String, format: `cluster#service`)
- TTL: `ttl` (Number, auto-delete after 7 days)

### AWS SES Configuration

For email notifications:

1. **Verify Sender Email**:
```bash
aws ses verify-email-identity --email-address no-reply@yourdomain.com
```

2. **Verify Domain** (optional but recommended):
```bash
aws ses verify-domain-identity --domain yourdomain.com
```

3. **Move Out of Sandbox** (for production):
   - Request production access in AWS SES console
   - Allows sending to any email address

## Usage Examples

### 1. Adding an AWS Account

**Via Web UI**:
1. Navigate to `/add-account`
2. Select authentication method (Access Keys, Profile, IAM Role, etc.)
3. Fill in account details
4. Click "Add Account & Start Monitoring"

**Via API**:
```bash
curl -X POST http://localhost:8000/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": "123456789012",
    "account_name": "production",
    "region": "us-east-1",
    "role_arn": "arn:aws:iam::123456789012:role/ECSMonitoringRole"
  }'
```

### 2. Viewing Analytics Dashboard

Access the main dashboard at `http://localhost:8000/`:

- **Total Accounts**: Number of monitored AWS accounts
- **Active Clusters**: ECS clusters discovered
- **Total Services**: Running ECS services
- **Health Distribution**: Services by health status (good/warning/critical)
- **Priority Breakdown**: Recommendations by priority level
- **Recent Recommendations**: Latest AI-generated insights

### 3. Generating Service Recommendations

**For All Services in an Account**:
```bash
curl http://localhost:8000/cluster-recommendations/123456789012
```

**For a Specific Cluster**:
```bash
curl http://localhost:8000/cluster-recommendations/123456789012/prod-cluster
```

**Response Example**:
```json
{
  "account_id": "123456789012",
  "cluster_name": "prod-cluster",
  "timestamp": "2024-01-15T10:30:00Z",
  "services": [
    {
      "service_name": "api-service",
      "service_health": "warning",
      "scaling_action": "scale_up",
      "priority": "high",
      "reason": "High CPU utilization (85%) with degraded response times",
      "recommendations": [
        "Increase desired task count from 3 to 5",
        "Consider increasing CPU allocation from 512 to 1024",
        "Monitor memory usage - currently at 78%",
        "Review application logs for OutOfMemory errors",
        "Enable auto-scaling with target CPU of 70%"
      ]
    }
  ],
  "summary": {
    "total_services": 12,
    "health_distribution": {
      "good": 8,
      "warning": 3,
      "critical": 1
    }
  }
}
```

### 4. Filtering Recommendations

**By Health Status**:
```bash
# Get only critical services
curl http://localhost:8000/service-recommendations/123456789012?health_status=critical

# Get warning services
curl http://localhost:8000/service-recommendations/123456789012?health_status=warning
```

**By Priority**:
```bash
# Get high-priority recommendations
curl http://localhost:8000/service-recommendations/123456789012?priority=high
```

**Combined Filters**:
```bash
# Critical services with high priority
curl http://localhost:8000/service-recommendations/123456789012?health_status=critical&priority=high
```

### 5. Interactive AI Chat

Ask questions about your infrastructure:

```bash
curl -X POST http://localhost:8000/chat/123456789012 \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Why is api-service showing high CPU? Should I scale up or optimize the code?",
    "context": {
      "service_name": "api-service",
      "cluster_name": "prod-cluster",
      "service_health": "warning",
      "scaling_action": "scale_up"
    }
  }'
```

**AI Response Example**:
```json
{
  "response": "Based on the metrics, api-service is experiencing high CPU (85% average, 92% peak) combined with elevated response times (1.2s average). This suggests the service is genuinely under load rather than inefficient code. Here's my analysis:\n\n1. **Immediate Action**: Scale up from 3 to 5 tasks to handle current load\n2. **Root Cause**: Request volume increased 40% over the past week\n3. **Long-term**: Implement auto-scaling with target CPU of 70%\n4. **Code Review**: Check for N+1 queries or inefficient database calls\n\nThe combination of high CPU + slow response times indicates capacity issues, not just code inefficiency.",
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### 6. Sending Email Reports

**Manual Trigger**:
```bash
# Send high-priority report
curl -X POST http://localhost:8000/trigger-daily-report

# Send comprehensive weekly report
curl -X POST http://localhost:8000/trigger-weekly-report
```

**Automated Schedule**:
- **Daily 7:00 AM**: Generate recommendations for all accounts
- **Daily 9:00 AM**: Email high-priority services only
- **Monday 8:00 AM**: Generate comprehensive recommendations
- **Monday 10:00 AM**: Email all recommendations grouped by priority

### 7. Exporting to Excel

Generate detailed Excel reports with cluster sheets:

```bash
curl http://localhost:8000/export-excel/123456789012 \
  --output ecs-report.xlsx
```

**Excel Structure**:
- One sheet per cluster
- Columns: Service Name, Status, Tasks, CPU, Memory, Target Groups, Health, Priority
- Top 5 AI recommendations per service

### 8. Refreshing Account Data

Force refresh of cluster and service data:

```bash
curl -X POST http://localhost:8000/accounts/123456789012/refresh
```

This bypasses the 24-hour cache and fetches fresh data from AWS.


## Best Practices Followed

### 1. **Centralized Configuration**

All configuration values are centralized in `config.py` with environment variable support:

```python
class Config:
    # AWS Configuration
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

    # Metrics Configuration
    METRICS_PERIOD = int(os.getenv('METRICS_PERIOD', '3600'))  # 1 hour
    METRICS_DAYS = int(os.getenv('METRICS_DAYS', '7'))  # 7 days

    # AI Configuration
    AI_MAX_TOKENS = int(os.getenv('AI_MAX_TOKENS', '4096'))
    AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0.7'))

    # Thresholds
    CPU_THRESHOLD_HIGH = float(os.getenv('CPU_THRESHOLD_HIGH', '80.0'))
    MEMORY_THRESHOLD_HIGH = float(os.getenv('MEMORY_THRESHOLD_HIGH', '80.0'))
    RESPONSE_TIME_THRESHOLD = float(os.getenv('RESPONSE_TIME_THRESHOLD', '1.0'))
```

**Benefits**:
- Easy to modify thresholds without code changes
- Environment-specific configuration (dev/staging/prod)
- Type safety with default values

### 2. **Structured Logging**

Consistent logging across all modules using `logger_config.py`:

```python
import logging

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
```

**Usage**:
```python
from logger_config import setup_logger
logger = setup_logger(__name__)

logger.info("Starting cluster analysis")
logger.error(f"Failed to fetch metrics: {error}", exc_info=True)
```

### 3. **Error Handling with Fallbacks**

Every critical operation has fallback logic:

```python
try:
    # Try AI-powered recommendations
    recommendations = await ai_recommender.generate_recommendations(metrics, logs)
except Exception as e:
    logger.error(f"AI recommendation failed: {e}")
    # Fallback to rule-based recommendations
    recommendations = self._fallback_recommendations(metrics)
```

**Fallback Strategies**:
- AI unavailable → Rule-based recommendations
- CloudWatch API failure → Use cached data
- DynamoDB error → Return in-memory results
- Email failure → Log error, continue processing

### 4. **API Rate Limiting**

Protect the application from abuse using SlowAPI:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/accounts")
@limiter.limit("100/minute")  # Read operations
async def get_accounts(request: Request):
    ...

@app.post("/accounts")
@limiter.limit("10/minute")  # Write operations
async def add_account(request: Request, account: AWSAccount):
    ...
```

### 5. **Async/Await for Concurrency**

Leverage Python's asyncio for parallel processing:

```python
# Sequential (slow)
for service in services:
    result = await process_service(service)  # 5 seconds each
# Total: 50 services × 5 seconds = 250 seconds

# Parallel (fast)
results = await asyncio.gather(
    *[process_service(service) for service in services]
)
# Total: ~5 seconds (limited by slowest service)
```

### 6. **Comprehensive API Documentation**

FastAPI automatically generates OpenAPI documentation:

```python
app = FastAPI(
    title="ECS Monitoring & AI Recommendations",
    description="Comprehensive ECS monitoring with AI-powered insights",
    version="1.0.0",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc
    openapi_url="/api/openapi.json"
)
```

Access interactive docs at `http://localhost:8000/api/docs`

### 7. **Health Check Endpoint**

Essential for load balancers and monitoring:

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }
```

### 8. **Graceful Shutdown**

Properly clean up resources on application shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    scheduler.start()

    yield

    # Shutdown
    logger.info("Shutting down gracefully...")
    if scheduler.running:
        scheduler.shutdown(wait=True)
    # Close database connections, flush logs, etc.
```

### 9. **Data Validation with Pydantic**

Type-safe request/response models:

```python
from pydantic import BaseModel

class AWSAccount(BaseModel):
    account_id: str
    account_name: str
    region: str = "us-east-1"
    access_key: Optional[str] = ""
    secret_key: Optional[str] = ""

    class Config:
        schema_extra = {
            "example": {
                "account_id": "123456789012",
                "account_name": "production",
                "region": "us-east-1"
            }
        }
```

### 10. **CI/CD Pipeline**

Automated testing and deployment using GitHub Actions:

```yaml
name: CI/CD Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pip install -r requirements-dev.txt
          pytest tests/

      - name: Lint code
        run: |
          flake8 .
          black --check .

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t ecs-monitoring .

      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login ...
          docker push ...
```

## Security & Performance Considerations

### Security Best Practices

#### 1. **Credential Management**

**Never hardcode credentials**:
```python
# ❌ Bad
access_key = "AKIAIOSFODNN7EXAMPLE"

# ✅ Good
access_key = os.getenv('AWS_ACCESS_KEY_ID')
```

**Prefer IAM roles over access keys**:
```python
# Production deployment on ECS/EC2
# No credentials needed - uses instance profile
session = boto3.Session(region_name='us-east-1')
```

**Use AWS Secrets Manager for sensitive data**:
```python
secrets_client = boto3.client('secretsmanager')
secret = secrets_client.get_secret_value(SecretId='ecs-monitoring/credentials')
credentials = json.loads(secret['SecretString'])
```

#### 2. **Cross-Account Access**

Use IAM roles with external IDs for security:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::MONITORING_ACCOUNT:role/ECSMonitoringRole"
    },
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {
        "sts:ExternalId": "ecs-monitoring-app"
      }
    }
  }]
}
```

**Why External ID?** Prevents the "confused deputy" problem where an attacker tricks your application into accessing their resources.

#### 3. **Least Privilege IAM Policies**

Grant only necessary permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:DescribeServices"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*",
      "Condition": {
        "StringEquals": {
          "cloudwatch:namespace": ["AWS/ECS", "AWS/ApplicationELB"]
        }
      }
    }
  ]
}
```

#### 4. **Authentication & Authorization**

**Cognito JWT Validation**:
```python
def verify_cognito_token(request: Request) -> dict:
    token = request.headers.get('x-amzn-oidc-data')
    if not token:
        raise HTTPException(401, "Missing authentication token")

    # Verify JWT signature using Cognito public keys
    jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json"
    jwks = requests.get(jwks_url).json()

    # Decode and verify
    claims = jwt.decode(token, jwks, algorithms=['ES256'])
    return claims
```

**Optional Authentication for Development**:
```python
DISABLE_AUTH = os.getenv('DISABLE_AUTH', 'false').lower() == 'true'

async def get_current_user(request: Request):
    if DISABLE_AUTH:
        return {"email": "dev@localhost", "name": "Developer"}
    return verify_cognito_token(request)
```

#### 5. **Data Encryption**

**DynamoDB Encryption at Rest**:
```python
dynamodb.create_table(
    TableName='ecs-service-recommendation',
    SSESpecification={
        'Enabled': True,
        'SSEType': 'KMS',
        'KMSMasterKeyId': 'alias/aws/dynamodb'
    }
)
```

**HTTPS in Production**:
```python
# Use ALB with SSL certificate
# Redirect HTTP to HTTPS
if not request.url.scheme == 'https' and not DISABLE_AUTH:
    return RedirectResponse(
        url=request.url.replace(scheme='https'),
        status_code=301
    )
```

### Performance Optimizations

#### 1. **Caching Strategy**

**24-Hour Cache for Cluster Data**:
```python
# Check cache first
cached_data = await knowledge_db.get_cluster_data(account_id)
if cached_data and not force_refresh:
    return cached_data

# Fetch fresh data
cluster_data = await monitor.get_cluster_details()
await knowledge_db.store_cluster_data(account_id, cluster_data, ttl=86400)
```

**Benefits**:
- Reduces CloudWatch API calls (cost savings)
- Faster response times (no AWS API latency)
- Respects AWS API rate limits

#### 2. **Batch Processing**

**Process services in batches**:
```python
# AWS limit: 10 services per describe_services call
BATCH_SIZE = 10

for i in range(0, len(service_arns), BATCH_SIZE):
    batch = service_arns[i:i+BATCH_SIZE]
    services = ecs.describe_services(cluster=cluster, services=batch)
    # Process batch...
```

#### 3. **Connection Pooling**

**Reuse boto3 sessions**:
```python
# ❌ Bad - creates new connection each time
def get_metrics():
    client = boto3.client('cloudwatch')
    return client.get_metric_statistics(...)

# ✅ Good - reuse session
class ECSMonitor:
    def __init__(self):
        self.cloudwatch = session.client('cloudwatch')

    def get_metrics(self):
        return self.cloudwatch.get_metric_statistics(...)
```

#### 4. **Async I/O for Network Calls**

**Don't block on I/O**:
```python
# ❌ Blocking
def get_all_metrics():
    results = []
    for service in services:
        metrics = cloudwatch.get_metric_statistics(...)  # Blocks
        results.append(metrics)
    return results

# ✅ Non-blocking
async def get_all_metrics():
    tasks = [
        asyncio.to_thread(cloudwatch.get_metric_statistics, ...)
        for service in services
    ]
    return await asyncio.gather(*tasks)
```

#### 5. **Pagination for Large Datasets**

**Frontend pagination**:
```python
@app.get("/accounts")
async def get_accounts(page: int = 1, limit: int = 10):
    total = len(all_accounts)
    start = (page - 1) * limit
    end = start + limit

    return {
        "accounts": all_accounts[start:end],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit
        }
    }
```

#### 6. **Database Indexing**

**DynamoDB GSI for queries**:
```python
# Query by health status efficiently
table.query(
    IndexName='health-status-index',
    KeyConditionExpression='account_id = :account AND service_health = :health',
    ExpressionAttributeValues={
        ':account': account_id,
        ':health': 'critical'
    }
)
```


## Common Pitfalls & Troubleshooting

### Issue 1: Empty Metrics Arrays

**Symptom**: Services show 0% CPU and memory, empty metrics arrays

**Causes**:
1. Service hasn't been running long enough (need 7 days of data)
2. CloudWatch metrics not enabled for ECS
3. IAM permissions missing for CloudWatch
4. Cross-account role lacks proper permissions

**Solution**:
```bash
# Verify CloudWatch permissions
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=your-service Name=ClusterName,Value=your-cluster \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-08T00:00:00Z \
  --period 3600 \
  --statistics Average

# Check ECS service configuration
aws ecs describe-services \
  --cluster your-cluster \
  --services your-service \
  --query 'services[0].enableECSManagedTags'
```

**Fix**:
- Wait 7 days for metrics to accumulate
- Enable CloudWatch Container Insights
- Add `cloudwatch:GetMetricStatistics` to IAM policy
- Verify cross-account role trust relationship

### Issue 2: Session Token Expiration

**Symptom**: `ExpiredToken` errors after 1 hour

**Cause**: Storing boto3 clients globally with temporary credentials

**Solution**: Create clients at runtime, not at startup
```python
# ❌ Bad - stored globally
ecs_monitors = {}
for account in accounts:
    ecs_monitors[account_id] = ECSMonitor(credentials)

# ✅ Good - created on demand
async def get_monitor(account_id: str) -> ECSMonitor:
    account_info = await knowledge_db.get_account(account_id)
    return ECSMonitor(
        access_key=account_info['access_key'],
        secret_key=account_info['secret_key'],
        session_token=account_info.get('session_token')
    )
```

### Issue 3: AWS API Rate Limiting

**Symptom**: `ThrottlingException` or `RequestLimitExceeded`

**Causes**:
- Too many concurrent API calls
- Fetching metrics for hundreds of services simultaneously
- No exponential backoff

**Solution**: Implement rate limiting and retries
```python
from botocore.config import Config
from botocore.exceptions import ClientError
import time

config = Config(
    retries={
        'max_attempts': 5,
        'mode': 'adaptive'  # Exponential backoff
    }
)

cloudwatch = session.client('cloudwatch', config=config)

# Add delays between batches
for batch in service_batches:
    process_batch(batch)
    await asyncio.sleep(0.5)  # 500ms delay
```

### Issue 4: Bedrock Model Access Denied

**Symptom**: `AccessDeniedException` when calling Bedrock

**Causes**:
1. Model not enabled in your AWS region
2. IAM permissions missing
3. Incorrect model ID format

**Solution**:
```bash
# Check available models
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`)].modelId'

# Request model access in AWS Console
# Bedrock → Model access → Request access

# Verify IAM permissions
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": "arn:aws:bedrock:*:*:inference-profile/*"
}
```

### Issue 5: DynamoDB Provisioned Throughput Exceeded

**Symptom**: `ProvisionedThroughputExceededException`

**Causes**:
- Writing too many recommendations simultaneously
- Table in provisioned mode with low capacity

**Solution**: Use on-demand billing or increase capacity
```python
# Switch to on-demand billing
dynamodb.update_table(
    TableName='ecs-service-recommendation',
    BillingMode='PAY_PER_REQUEST'
)

# Or increase provisioned capacity
dynamodb.update_table(
    TableName='ecs-service-recommendation',
    ProvisionedThroughput={
        'ReadCapacityUnits': 25,
        'WriteCapacityUnits': 25
    }
)
```

### Issue 6: Large Cluster Timeout

**Symptom**: Request timeout when analyzing clusters with 100+ services

**Causes**:
- Sequential processing taking too long
- API gateway timeout (30 seconds)
- No progress indication

**Solution**: Use background tasks and webhooks
```python
@app.post("/cluster-recommendations/{account_id}")
async def start_analysis(account_id: str, background_tasks: BackgroundTasks):
    # Start analysis in background
    background_tasks.add_task(analyze_cluster, account_id)

    return {
        "status": "started",
        "message": "Analysis running in background",
        "check_status_url": f"/analysis-status/{account_id}"
    }

async def analyze_cluster(account_id: str):
    # Long-running analysis
    results = await process_all_services(account_id)

    # Store results
    await knowledge_db.store_results(account_id, results)

    # Notify via webhook
    await notify_completion(account_id)
```

### Issue 7: Cognito JWT Verification Failure

**Symptom**: `401 Unauthorized` despite valid login

**Causes**:
1. ALB not configured to pass JWT token
2. Wrong Cognito configuration
3. Token expired

**Debug Steps**:
```bash
# Check headers
curl http://localhost:8000/debug/headers

# Verify Cognito configuration
echo $COGNITO_REGION
echo $COGNITO_USER_POOL_ID
echo $COGNITO_CLIENT_ID

# Test token manually
curl http://localhost:8000/debug/oauth-test
```

**Solution**:
```python
# Add detailed logging
logger.debug(f"Headers: {dict(request.headers)}")
logger.debug(f"JWT token present: {'x-amzn-oidc-data' in request.headers}")

# Verify JWKS endpoint
jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/jwks.json"
response = requests.get(jwks_url)
logger.debug(f"JWKS response: {response.status_code}")
```

### Issue 8: High Memory Usage

**Symptom**: Application consuming excessive memory (>2GB)

**Causes**:
- Storing all metrics in memory
- Not releasing boto3 clients
- Large chat history accumulation

**Solution**: Implement memory limits
```python
# Limit chat history
MAX_CHAT_HISTORY = 20
if len(chat_history[account_id]) > MAX_CHAT_HISTORY:
    chat_history[account_id] = chat_history[account_id][-MAX_CHAT_HISTORY:]

# Stream large responses
@app.get("/export-excel/{account_id}")
async def export_excel(account_id: str):
    def generate():
        # Generate Excel in chunks
        for chunk in create_excel_chunks(account_id):
            yield chunk

    return StreamingResponse(generate(), media_type='application/vnd.ms-excel')

# Clear unused clients
del ecs_monitor
gc.collect()
```

### Debugging Tips

**Enable Debug Logging**:
```bash
export LOG_LEVEL=DEBUG
python app.py
```

**Test Individual Components**:
```python
# Test ECS monitor
monitor = ECSMonitor(region='us-east-1')
clusters = monitor._get_all_clusters()
print(f"Found {len(clusters)} clusters")

# Test AI recommender
recommender = AIRecommender()
response = await recommender.generate_recommendations(metrics, logs)
print(json.dumps(response, indent=2))

# Test DynamoDB connection
db = KnowledgeDB()
accounts = await db.get_all_accounts()
print(f"Stored accounts: {len(accounts)}")
```

**Monitor AWS API Calls**:
```python
import boto3
from botocore.config import Config

# Enable debug logging for boto3
boto3.set_stream_logger('boto3.resources', logging.DEBUG)

# Track API calls
config = Config(
    signature_version='v4',
    retries={'max_attempts': 3}
)
```

## Enhancements & Future Improvements

### Short-Term Enhancements (1-3 months)

#### 1. **Anomaly Detection**
Use statistical models to detect unusual patterns:

```python
from scipy import stats

def detect_anomalies(metrics: List[float]) -> List[int]:
    """Detect anomalies using Z-score"""
    z_scores = stats.zscore(metrics)
    threshold = 3  # 3 standard deviations

    anomalies = []
    for i, z in enumerate(z_scores):
        if abs(z) > threshold:
            anomalies.append(i)

    return anomalies

# Usage
cpu_values = [dp['Average'] for dp in service_metrics['cpu']]
anomaly_indices = detect_anomalies(cpu_values)

if anomaly_indices:
    logger.warning(f"CPU anomalies detected at indices: {anomaly_indices}")
```

#### 2. **Cost Analysis**
Calculate actual AWS costs based on resource usage:

```python
def calculate_service_cost(service_metrics: Dict) -> float:
    """Estimate monthly cost for ECS service"""
    # Fargate pricing: $0.04048 per vCPU per hour
    # $0.004445 per GB per hour

    cpu_units = service_metrics['task_definition']['cpu']  # e.g., 1024 = 1 vCPU
    memory_gb = int(service_metrics['task_definition']['memory']) / 1024
    task_count = service_metrics['desired_count']

    vcpu_cost = (cpu_units / 1024) * 0.04048 * 730  # hours per month
    memory_cost = memory_gb * 0.004445 * 730

    monthly_cost = (vcpu_cost + memory_cost) * task_count
    return round(monthly_cost, 2)
```

#### 3. **Slack/Teams Integration**
Send notifications to collaboration tools:

```python
import requests

async def send_slack_notification(webhook_url: str, recommendations: Dict):
    """Send recommendations to Slack"""
    critical_services = [
        rec for rec in recommendations['services']
        if rec['service_health'] == 'critical'
    ]

    message = {
        "text": f"🚨 {len(critical_services)} Critical ECS Services Detected",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Critical Services:*\n" +
                           "\n".join([f"• {s['service_name']}" for s in critical_services])
                }
            }
        ]
    }

    requests.post(webhook_url, json=message)
```

#### 4. **Predictive Scaling**
Use machine learning to predict future resource needs:

```python
from sklearn.linear_model import LinearRegression
import numpy as np

def predict_cpu_usage(historical_metrics: List[Dict]) -> float:
    """Predict CPU usage for next hour"""
    # Extract timestamps and CPU values
    X = np.array([i for i in range(len(historical_metrics))]).reshape(-1, 1)
    y = np.array([m['Average'] for m in historical_metrics])

    # Train model
    model = LinearRegression()
    model.fit(X, y)

    # Predict next value
    next_index = len(historical_metrics)
    predicted_cpu = model.predict([[next_index]])[0]

    return round(predicted_cpu, 2)
```

### Medium-Term Enhancements (3-6 months)

#### 5. **Multi-Region Support**
Monitor services across multiple AWS regions:

```python
class MultiRegionMonitor:
    def __init__(self, regions: List[str]):
        self.monitors = {
            region: ECSMonitor(region=region)
            for region in regions
        }

    async def get_global_metrics(self) -> Dict:
        """Aggregate metrics across all regions"""
        tasks = [
            monitor.get_cluster_metrics()
            for monitor in self.monitors.values()
        ]

        regional_metrics = await asyncio.gather(*tasks)

        return {
            region: metrics
            for region, metrics in zip(self.monitors.keys(), regional_metrics)
        }
```

#### 6. **Custom Alerting Rules**
Allow users to define custom alert conditions:

```python
class AlertRule:
    def __init__(self, name: str, condition: str, action: str):
        self.name = name
        self.condition = condition  # e.g., "cpu_avg > 80 AND memory_avg > 75"
        self.action = action  # e.g., "send_email" or "scale_up"

    def evaluate(self, metrics: Dict) -> bool:
        """Evaluate rule against metrics"""
        # Parse condition and evaluate
        cpu_avg = metrics.get('cpu_avg', 0)
        memory_avg = metrics.get('memory_avg', 0)

        # Safe eval with limited scope
        return eval(self.condition, {
            'cpu_avg': cpu_avg,
            'memory_avg': memory_avg
        })

# Usage
rule = AlertRule(
    name="High Resource Usage",
    condition="cpu_avg > 80 and memory_avg > 75",
    action="send_email"
)

if rule.evaluate(service_metrics):
    await execute_action(rule.action, service_metrics)
```

#### 7. **Grafana Integration**
Export metrics to Grafana for advanced visualization:

```python
from prometheus_client import Gauge, CollectorRegistry, push_to_gateway

registry = CollectorRegistry()
cpu_gauge = Gauge('ecs_cpu_utilization', 'ECS CPU Utilization',
                  ['cluster', 'service'], registry=registry)
memory_gauge = Gauge('ecs_memory_utilization', 'ECS Memory Utilization',
                     ['cluster', 'service'], registry=registry)

async def export_to_prometheus(metrics: Dict):
    """Export metrics to Prometheus Pushgateway"""
    for cluster, services in metrics.items():
        for service in services:
            cpu_gauge.labels(cluster=cluster, service=service['name']).set(
                service['cpu_avg']
            )
            memory_gauge.labels(cluster=cluster, service=service['name']).set(
                service['memory_avg']
            )

    push_to_gateway('localhost:9091', job='ecs-monitoring', registry=registry)
```

### Long-Term Vision (6-12 months)

#### 8. **Auto-Remediation**
Automatically apply recommendations:

```python
async def auto_remediate(recommendation: Dict):
    """Automatically apply scaling recommendations"""
    if recommendation['scaling_action'] == 'scale_up':
        # Update ECS service
        ecs.update_service(
            cluster=recommendation['cluster'],
            service=recommendation['service'],
            desiredCount=recommendation['suggested_capacity']['desired_count']
        )

        logger.info(f"Auto-scaled {recommendation['service']} to "
                   f"{recommendation['suggested_capacity']['desired_count']} tasks")
```

#### 9. **Kubernetes Support**
Extend monitoring to EKS clusters:

```python
from kubernetes import client, config

class K8sMonitor:
    def __init__(self):
        config.load_kube_config()
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()

    async def get_pod_metrics(self, namespace: str) -> List[Dict]:
        """Get metrics for all pods in namespace"""
        pods = self.v1.list_namespaced_pod(namespace)

        metrics = []
        for pod in pods.items:
            metrics.append({
                'name': pod.metadata.name,
                'status': pod.status.phase,
                'cpu_request': pod.spec.containers[0].resources.requests.get('cpu'),
                'memory_request': pod.spec.containers[0].resources.requests.get('memory')
            })

        return metrics
```

#### 10. **AI Model Fine-Tuning**
Train custom models on your infrastructure patterns:

```python
# Collect training data from historical recommendations
training_data = []
for recommendation in historical_recommendations:
    training_data.append({
        'input': {
            'cpu_avg': recommendation['metrics']['cpu_avg'],
            'memory_avg': recommendation['metrics']['memory_avg'],
            'response_time': recommendation['metrics']['response_time']
        },
        'output': {
            'action': recommendation['action'],
            'success': recommendation['was_successful']
        }
    })

# Fine-tune Claude on your data
# (Requires AWS Bedrock custom model training)
```

## Conclusion

Building a production-ready ECS monitoring system requires careful consideration of scalability, reliability, and user experience. Key takeaways:

### What We Built
- **Multi-account monitoring** with flexible authentication
- **AI-powered recommendations** using AWS Bedrock Claude Sonnet 4
- **Comprehensive metrics** from ECS, CloudWatch, and ALB
- **Automated reporting** with daily and weekly schedules
- **Interactive dashboards** for real-time insights

### Lessons Learned

1. **Pagination is Critical**: AWS APIs have strict limits. Always implement pagination for production systems.

2. **Session Management Matters**: Don't store boto3 clients globally when using temporary credentials. Create them on-demand.

3. **AI Needs Fallbacks**: Bedrock can fail or return malformed responses. Always have rule-based fallbacks.

4. **Async is Essential**: Processing hundreds of services sequentially is too slow. Use asyncio for parallelism.

5. **Caching Saves Money**: CloudWatch API calls add up quickly. Cache aggressively with appropriate TTLs.

6. **Observability First**: Comprehensive logging and error handling make debugging production issues manageable.

### Production Readiness Checklist

- ✅ Multi-account support with IAM roles
- ✅ Error handling with fallbacks
- ✅ Rate limiting and retry logic
- ✅ Comprehensive logging
- ✅ Health check endpoints
- ✅ API documentation (OpenAPI/Swagger)
- ✅ Docker containerization
- ✅ CI/CD pipeline
- ✅ Security best practices (least privilege IAM, encryption)
- ✅ Performance optimization (caching, async, batching)

### Next Steps

1. **Deploy to Production**: Use ECS Fargate with IAM roles for credentials
2. **Enable Monitoring**: Set up CloudWatch alarms for the monitoring system itself
3. **Gather Feedback**: Let your team use it and iterate based on real needs
4. **Extend Coverage**: Add support for Lambda, RDS, or other AWS services
5. **Contribute**: Open source your improvements to help the community

### Resources

- **GitHub Repository**: [aws-ecs-service-recommendations](https://github.com/yourusername/aws-ecs-service-recommendations)
- **AWS Documentation**: [ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- **Bedrock Guide**: [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- **FastAPI Docs**: [FastAPI Official Documentation](https://fastapi.tiangolo.com/)

---

**Built with ❤️ using FastAPI, AWS Bedrock Claude Sonnet 4, and modern cloud-native technologies**

---

## Contact & Support

**Author**: Prashant Gupta
**GitHub**: https://github.com/prashantgupta123/
**LinkedIn**: https://www.linkedin.com/in/prashantgupta123/

**Questions or feedback?** Open an issue or submit a pull request!

---

*This solution is part of the [AWS ECS Service Recommendations](https://github.com/prashantgupta123/aws-ecs-service-recommendations) repository—a comprehensive collection of production-ready automation tools for cloud infrastructure management.*

**⭐ If you found this helpful, please star the repository!**

---
