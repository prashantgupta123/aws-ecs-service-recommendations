# 🏗️ ECS Monitoring & AI Recommendations System

A comprehensive web application that monitors AWS ECS infrastructure across multiple accounts and provides AI-powered recommendations using AWS Bedrock Claude Sonnet 4.

## 📊 **New: Recommendations Dashboard**
- **Centralized View**: Access all stored service recommendations in one place at `/recommendations-dashboard`
- **Priority Grouping**: Recommendations organized by priority (High → Medium → Low)
- **Health Status Sorting**: Within each priority, sorted by service health (Critical → Warning → Error → Good)
- **Collapsible Interface**: Expandable sections for focused viewing
- **Real-time Data**: Displays latest recommendations from knowledge base
- **Generate Latest Recommendations**: One-click button to trigger `/trigger-daily-recommendations` API for fresh data
- **Auto-refresh**: Automatically refreshes dashboard after generating new recommendations
- **Left Sidebar Navigation**: Easy navigation between Dashboard, Recommendations, and Add Account with persistent sidebar
- **Responsive Design**: Mobile-friendly sidebar that collapses on smaller screens

## 📈 **New: Analytics Dashboard**
- **Comprehensive Overview**: High-level analytics at `/analytics-dashboard` with data from both knowledge base tables
- **Interactive Charts**: Beautiful Chart.js visualizations for health distribution, priority levels, and scaling actions
- **Real-time Statistics**: Live metrics including total accounts, clusters, services, and recommendations
- **Account Overview Table**: Detailed table showing all monitored accounts with cluster/service counts
- **Recent Recommendations**: Grid view of latest service recommendations with priority and health badges
- **Visual Insights**: Pie charts, bar charts, and doughnut charts for data visualization
- **Responsive Design**: Mobile-friendly charts and tables that adapt to screen size
- **Auto-refresh**: Automatic data refresh every 5 minutes with manual refresh option

## 🎯 **New: Cluster Analysis Dashboard**
- **Targeted Analysis**: Dedicated dashboard at `/cluster-dashboard` for analyzing specific ECS clusters
- **Account Selection**: Dropdown to select AWS accounts from knowledge base
- **Cluster Input**: Text field to specify exact cluster name for focused analysis
- **Service-Level Recommendations**: Generate AI recommendations for all services within the selected cluster
- **Real-time Processing**: Live generation of recommendations using existing `/cluster-recommendations/{account_id}` API
- **Comprehensive Results**: Display all services with health status, priority levels, and scaling actions
- **Detailed Analysis**: Show AI recommendations, service metrics, and scaling rationale for each service
- **Summary Statistics**: Cluster-level overview with health distribution and priority counts
- **Error Handling**: Clear error messages for invalid cluster names with available cluster suggestions

## ✨ Features

### 🔍 **Multi-Account Monitoring**
- Monitor ECS clusters across multiple AWS accounts in parallel
- Real-time cluster and service discovery with pagination support
- Automatic background monitoring every 5 minutes
- **Paginated Discovery**: Handles accounts with large numbers of clusters (>100) and clusters with large numbers of services (>10) using AWS API pagination

### 📊 **Advanced Metrics & Analytics**
- **ECS Metrics**: CPU and Memory utilization (average & maximum) via CloudWatch
- **Task Definition Analysis**: Comprehensive task definition details including:
  - Task family and revision information
  - Compatibility modes (EC2, Fargate)
  - Required compatibilities configuration
  - Task-level CPU and memory allocation
  - Container-level resource specifications (CPU, memory, memoryReservation)
- **Target Group Metrics**: Application Load Balancer health and performance tracking
  - Healthy/Unhealthy host counts (average & maximum)
  - Response time analysis (average & maximum)
  - Request volume monitoring (average & maximum)
  - **HTTP Status Code Tracking**: 2XX, 3XX, 4XX response counts
  - **Error Rate Analysis**: Automatic error percentage calculation (3XX + 4XX) / 2XX * 100
- Service-level performance metrics with peak detection
- Historical trend analysis and storage
- Task count and health monitoring
- Automatic ALB vs NLB detection (only ALB metrics collected)

### 🤖 **AI-Powered Recommendations**
- **Claude Sonnet 4** integration for intelligent analysis
- Service-specific scaling recommendations
- Account-wide optimization suggestions
- Performance issue detection and solutions
- Cost optimization recommendations

### 💬 **Interactive AI Chat**
- **Conversational AI** for discussing recommendations
- Context-aware responses about current ECS state
- Technical guidance on scaling scenarios
- Real-time Q&A about CPU, memory, and threading implications
- Follow-up discussions on optimization strategies

### 📧 **Automated Daily & Weekly Reports**
- **Daily Cluster Analysis**: Automatically generates service recommendations at 7:00 AM daily
- **Daily Email Reports**: Automatically sends high-priority reports at 9:00 AM daily
- **Weekly Cluster Analysis**: Automatically generates service recommendations at 8:00 AM on Mondays
- **Weekly Email Reports**: Automatically sends comprehensive reports at 10:00 AM on Mondays
- **High-Priority Focus**: Daily email reports only include services with priority=high
- **Comprehensive Weekly**: Weekly reports include all services grouped by priority
- **HTML Email Format**: Professional email templates matching AI recommendation theme
- **Summary Statistics**: Critical/warning service counts and scaling recommendations
- **Configurable Scheduling**: Enable/disable daily and weekly crons via environment variables
- **Manual Triggers**: Test endpoints available for immediate execution

### 📋 **Log Analysis**
- Automated log review and pattern detection
- Error rate monitoring and alerting
- Service-specific log analysis
- Real-time log streaming from CloudWatch

### 💾 **Knowledge Database**
- Historical data storage in DynamoDB
- **Service Recommendations Storage**: New `ecs-service-recommendation` table for individual service analysis
- **Health Status Tracking**: Monitor service health (good|warning|critical|error) with scaling actions
- **Priority-based Filtering**: Categorize recommendations by priority (high|medium|low)
- Persistent account storage (survives app restarts)
- Learning from past recommendations
- Trend analysis for predictive insights
- Automatic data retention policies
- On-demand data refresh functionality

### 🎨 **Beautiful Web Dashboard**
- Modern, responsive UI with gradient design and left sidebar navigation
- Individual service cards with metrics
- Modal popups for detailed recommendations
- Real-time status updates and loading indicators
- Refresh button for on-demand data updates
- Persistent account management
- **Left Sidebar Navigation**: Quick access to Dashboard (🏠), Recommendations (📊), and Add Account (➕) pages
- **Mobile Responsive**: Collapsible sidebar with hamburger menu on mobile devices
- **Dedicated Add Account Page**: Clean, focused interface for adding AWS accounts at `/add-account`
- **Optimized Services Dashboard**: Pagination, filtering, and lazy loading for better performance with multiple accounts
- **Search & Filter**: Real-time search by account name/ID and status filtering (active/inactive)
- **Pagination Controls**: Configurable items per page (2, 5, 10, 20) with navigation controls
- **Lazy Loading**: Cluster details loaded on-demand to improve initial page load time

## 🚀 Quick Start

### Option 1: Docker (Recommended)
```bash
# Build and run with Docker
docker build -t aws-ecs-recommendations .
docker run -p 8000:8000 aws-ecs-recommendations

# Or use docker-compose
docker-compose up -d
```

### Option 2: Local Development
```bash
# Install dependencies (Python 3.13+ required)
pip install -r requirements.txt

# For local development without authentication
export DISABLE_AUTH=true

# Run application
python app.py

# Or use make commands
make dev  # Development mode with auto-reload
```

### 🌐 Access Dashboard
Open http://localhost:8000 in your browser (Analytics Dashboard is now the main page)

### ➕ Add AWS Account
1. Navigate to the **Add Account** page via the left sidebar or visit `/add-account`
2. Select authentication method:
   - **Access Key & Secret**: Traditional AWS credentials
   - **AWS Profile**: Use AWS CLI profiles
   - **IAM Role ARN**: Assume IAM roles
   - **Session Token**: Temporary credentials
   - **Default Credentials**: Environment/instance profile
3. Fill in the account form based on selected method
4. Click "Add Account & Start Monitoring"
5. System automatically discovers and monitors all ECS clusters
6. Redirects back to main dashboard upon successful addition

## 🏛️ Architecture

### Core Components
- **FastAPI**: High-performance web framework and API endpoints
- **ECSMonitor**: Parallel cluster monitoring with async processing
- **AIRecommender**: AWS Bedrock Claude Sonnet 4 integration
- **KnowledgeDB**: DynamoDB storage with automatic TTL
- **Dashboard**: Modern HTML5/CSS3/JavaScript frontend

### Data Flow
1. **Account Registration** → Credentials stored securely
2. **Cluster Discovery** → Automatic ECS cluster enumeration
3. **Parallel Monitoring** → Concurrent service monitoring
4. **Metrics Collection** → CloudWatch data aggregation
5. **Log Analysis** → Real-time log processing
6. **AI Analysis** → Claude Sonnet 4 recommendation generation
7. **Knowledge Storage** → Historical data persistence
8. **Dashboard Updates** → Real-time UI refresh

## ☁️ AWS Services Integration

| Service | Purpose | Usage |
|---------|---------|-------|
| **ECS** | Container orchestration | Cluster/service monitoring |
| **CloudWatch** | Metrics & logs | Performance data collection |
| **Bedrock** | AI recommendations | Claude Sonnet 4 analysis |
| **DynamoDB** | Knowledge database | Historical data storage + service recommendations |
| **SES** | Email notifications | Professional recommendation reports |
| **ELB v2** | Load balancer metrics | Target group health and performance |
| **IAM** | Access control | Service permissions |

### 📊 **Service Recommendation Database Schema**

**Table**: `ecs-service-recommendation`

| Column | Type | Description |
|--------|------|-------------|
| `account_id` | String (Hash Key) | AWS Account identifier |
| `service_cluster_key` | String (Range Key) | Format: `{cluster}#{service}` |
| `service` | String | ECS service name |
| `cluster` | String | ECS cluster name |
| `service_health` | String | Health status: `good\|warning\|critical\|error` |
| `scaling_action` | String | Recommended action: `scale_up\|scale_down\|no_change` |
| `priority` | String | Priority level: `high\|medium\|low` |
| `recommendations` | JSON | Full AI recommendation object |
| `timestamp` | String | ISO timestamp of analysis |
| `ttl` | Number | Auto-deletion after 7 days |

## 🔌 API Endpoints

### Dashboard
- `GET /` - Analytics dashboard (main page)
- `GET /services-dashboard` - Services dashboard page
- `GET /services-dashboard-optimized` - Optimized services dashboard with pagination and filtering
- `GET /add-account` - Add AWS account page
- `GET /recommendations-dashboard` - Recommendations dashboard page
- `GET /cluster-dashboard` - Cluster analysis dashboard page
- `GET /health` - Health check endpoint

### Account Management
- `POST /accounts` - Add AWS account for monitoring
- `GET /accounts` - List all monitored accounts with status
- `GET /accounts?page=1&limit=5&search=prod&status_filter=active` - List accounts with pagination and filtering
- `POST /accounts/{account_id}/refresh` - Refresh account data on-demand

### Service Details
- `GET /service-details/{account_id}/{cluster_name}/{service_name}` - Get detailed information for a specific service

### AI Recommendations
- `GET /recommendations/{account_id}` - Account-wide recommendations
- `GET /recommendations/{account_id}/{cluster_name}/{service_name}` - Service-specific recommendations
- `GET /cluster-recommendations/{account_id}` - Generate and store service recommendations for all services in all clusters
- `GET /cluster-recommendations/{account_id}/{cluster_name}` - Generate recommendations for a specific cluster only
- `GET /service-recommendations/{account_id}?health_status={status}&priority={priority}` - Get stored service recommendations filtered by health status and/or priority (high|medium|low)
- `GET /all-recommendations` - Get all service recommendations grouped by priority and health
- `GET /analytics-data` - Get comprehensive analytics data from both knowledge base tables

### AI Chat
- `POST /chat/{account_id}` - Interactive chat with AI about ECS scenarios and recommendations

### Email Notifications
- `POST /send-email/{account_id}` - Send professional email reports with recommendations
- `POST /trigger-daily-report` - Manually trigger daily high-priority reports (for testing)
- `POST /trigger-weekly-recommendations` - Manually trigger weekly cluster recommendations generation (for testing)
- `POST /trigger-weekly-report` - Manually trigger weekly comprehensive reports (for testing)
- **Daily Cron Jobs**: Automatically generates recommendations at 4:00 AM and sends high-priority reports at 5:00 AM daily
- **Weekly Cron Jobs**: Automatically generates recommendations at 6:00 AM and sends comprehensive reports at 7:00 AM on Mondays

### Excel Reports
- `GET /export-excel/{account_id}` - Generate Excel report with cluster sheets and service recommendations

### Service Health Analytics
- `GET /cluster-recommendations/{account_id}` - Comprehensive analysis of all services across clusters
- `GET /service-recommendations/{account_id}` - Retrieve all stored service recommendations
- `GET /service-recommendations/{account_id}?health_status=critical` - Filter by health status
- `GET /service-recommendations/{account_id}?priority=high` - Filter by priority level
- `GET /service-recommendations/{account_id}?health_status=warning&priority=high` - Combined filters

## 🐳 Docker Deployment

**Base Image**: Python 3.13-slim for optimal performance and security

### Quick Commands
```bash
# Build and run
make build && make run

# Or use docker-compose
make compose-up

# View logs
make logs

# Clean up
make clean
```

### Manual Docker Commands
```bash
# Build image
docker build -t aws-ecs-recommendations .

# Run with environment file
docker run -p 8000:8000 --env-file .env aws-ecs-recommendations

# Run with IAM role (recommended for production)
docker run -p 8000:8000 aws-ecs-recommendations
```

### Docker Compose
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

## ⚙️ Configuration

### Project Files
- `.env.example` - Environment variables template
- `.gitignore` - Git exclusion patterns
- `.dockerignore` - Docker build exclusions
- `docker-compose.yml` - Container orchestration
- `Makefile` - Development commands
- `pyproject.toml` - Python 3.13 project configuration

### Environment Variables
```bash
# Copy template and configure
cp .env.example .env

# Authentication Configuration
DISABLE_AUTH=false  # Set to 'true' for local development without authentication

# AWS Credentials (optional - can use IAM roles)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=ap-south-1

# Email Configuration (for SES notifications)
EMAIL_SOURCE=no-reply@cloudplatform.com
EMAIL_DESTINATION=prashantgupta036@gmail.com,team@cloudplatform.com
EMAIL_CC=manager@cloudplatform.com,admin@cloudplatform.com

# Cron Job Configuration
DAILY_RECOMMENDATIONS_CRON_ENABLED=true
WEEKLY_RECOMMENDATIONS_CRON_ENABLED=true

# Cognito Authentication (only required when DISABLE_AUTH=false)
COGNITO_REGION=ap-south-1
COGNITO_USER_POOL_ID=ap-south-1_UmgZ0gxyJ
COGNITO_CLIENT_ID=53h1fm5fgocp5cueait5fslfg9

# AI Model Configuration
BEDROCK_MODEL_NAME=apac.anthropic.claude-3-7-sonnet-20250219-v1:0

# Application Settings
LOG_LEVEL=INFO
PORT=8000
```

### Automatic Setup
The system automatically:
- Creates DynamoDB table `ecs-monitoring-knowledge`
- Loads existing accounts on startup (AI recommenders only)
- Creates ECS monitors at runtime to prevent session token expiration
- Monitors ECS clusters every 5 minutes
- Generates AI recommendations on demand
- Stores historical data with TTL policies
- Handles service discovery and health checks
- Persists account data across restarts
- Schedules daily and weekly cron jobs (configurable via environment variables)

### Email Setup Requirements
1. **SES Configuration**: Verify sender email in AWS SES console
2. **Domain Verification**: Verify sending domain (optional but recommended)
3. **IAM Permissions**: Add SES send permissions to application role
4. **Email Template**: Update sender email in `send_recommendations_email()` function
5. **Production Mode**: Move SES out of sandbox for unrestricted sending

### Cron Job Configuration
**Environment Variables**:
- `DAILY_RECOMMENDATIONS_CRON_ENABLED=true|false` - Enable/disable daily cron jobs
- `WEEKLY_RECOMMENDATIONS_CRON_ENABLED=true|false` - Enable/disable weekly cron jobs

**Daily Schedule**:
- 7:00 AM: Generate cluster recommendations for all accounts
- 9:00 AM: Send high-priority email reports

**Weekly Schedule**:
- Monday 8:00 AM: Generate comprehensive cluster recommendations
- Monday 10:00 AM: Send comprehensive email reports (all priorities)

**Manual Triggers**:
- `POST /trigger-daily-report` - Test daily high-priority reports
- `POST /trigger-weekly-recommendations` - Test weekly recommendations generation
- `POST /trigger-weekly-report` - Test weekly comprehensive reports

## 🔒 Security Best Practices

### Production Deployment
- ✅ **Preferred**: Use IAM roles or AWS profiles instead of access keys
- ✅ Enable encryption for DynamoDB table
- ✅ Implement proper authentication for web interface
- ✅ Use HTTPS in production
- ✅ Rotate AWS credentials regularly
- ✅ Apply least privilege IAM policies
- ✅ Secure credential storage for DynamoDB access

### Credential Management
**AWS Authentication Options** (in order of preference):

1. **IAM Roles** (Production recommended):
   - Deploy on EC2/ECS/Lambda with IAM role
   - No credentials needed in environment
   - Most secure approach

2. **AWS CLI Profiles**:
   - Configure `~/.aws/credentials`
   - Suitable for local development

3. **Environment Variables** (Docker/CI):
   ```bash
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   ```

4. **Instance/Container Credentials**:
   - Automatic credential discovery
   - Works with AWS services

**Account Authentication Methods**:
- **Access Keys**: Direct AWS access key and secret key
- **AWS Profiles**: Uses `~/.aws/credentials` profiles (`profile_name`)
- **IAM Role ARN**: Assumes roles via STS (`role_arn`)
- **Session Tokens**: Temporary credentials with session token
- **Default Credentials**: Environment variables, instance profiles, etc.

### Required IAM Permissions

All IAM policies are available in the `iam-policies.json` file. You can use individual policies or the combined policy:

- **ECSMonitoringPolicy**: ECS cluster and service monitoring permissions
- **DynamoDBKnowledgePolicy**: Knowledge database storage permissions
- **SESEmailNotificationPolicy**: Email notification permissions
- **CombinedECSMonitoringPolicy**: All permissions in one policy (recommended)

**Quick Setup**:
```bash
# Create IAM policy from JSON file
aws iam create-policy --policy-name ECSMonitoringPolicy \
  --policy-document file://iam-policies.json

# Attach to your IAM role/user
aws iam attach-role-policy --role-name YourRoleName \
  --policy-arn arn:aws:iam::ACCOUNT:policy/ECSMonitoringPolicy
```

## 🎯 Use Cases

- **DevOps Teams**: Monitor container infrastructure health across multiple AWS accounts
- **SRE Teams**: Proactive scaling and optimization with flexible authentication
- **Service Health Monitoring**: Track individual service health status with priority-based alerts
- **Automated Scaling Decisions**: AI-powered recommendations for scale_up/scale_down/no_change actions
- **Cost Optimization**: AI-driven resource right-sizing with priority categorization
- **Performance Monitoring**: Real-time service health tracking with critical/warning/good status
- **Capacity Planning**: Historical trend analysis with service-level granularity
- **Technical Consultations**: Interactive AI discussions about scaling decisions
- **Scenario Planning**: "What-if" analysis for resource changes
- **Multi-Account Management**: Support for various AWS authentication methods
- **Health Dashboard**: Filter services by health status for focused troubleshooting
- **Priority-based Operations**: Focus on high-priority recommendations first

## 🛠️ Development Commands

### Make Commands
```bash
make help          # Show all available commands
make install       # Install Python dependencies
make dev          # Run in development mode
make build        # Build Docker image
make run          # Run Docker container
make compose-up   # Start with docker-compose
make compose-down # Stop docker-compose
make logs         # View container logs
make clean        # Clean up Docker resources
```

### Manual Commands
```bash
# Local development (with authentication disabled)
DISABLE_AUTH=true pip install -r requirements.txt
DISABLE_AUTH=true uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Docker development
docker build -t aws-ecs-recommendations .
docker run -p 8000:8000 --env-file .env aws-ecs-recommendations

# Health check
curl http://localhost:8000/health
```

## 🔧 Troubleshooting

### Common Issues
1. **Bedrock Access**: Ensure Claude 3.5 Sonnet model access in your region
2. **IAM Permissions**: Verify all required permissions are granted
3. **Network Access**: Check security groups and VPC settings
4. **Log Access**: Ensure CloudWatch logs are properly configured
5. **DynamoDB Access**: Ensure AWS credentials are configured for knowledge database
6. **Account Persistence**: Accounts won't persist without DynamoDB credentials
7. **OAuth Authentication**: Check Cognito configuration and ALB integration
8. **Session Token Expiration**: ECS monitors are now created at runtime to prevent session token expiration

### Debug Endpoints
```bash
# Test basic functionality
curl https://your-domain.com/debug/simple

# Check request headers and OAuth tokens
curl https://your-domain.com/debug/headers

# Test OAuth authentication flow
curl https://your-domain.com/debug/oauth-test

# Check health status
curl https://your-domain.com/health
```

### OAuth/Authentication Issues
1. **500 Error on OAuth Callback**: Check Cognito configuration in environment variables
2. **Missing JWT Token**: Verify ALB is configured to pass `x-amzn-oidc-data` header
3. **Token Verification Failed**: Check COGNITO_REGION, COGNITO_USER_POOL_ID, and COGNITO_CLIENT_ID
4. **JWKS Fetch Error**: Ensure network connectivity to Cognito JWKS endpoint

### Role ARN Authentication Issues
1. **Empty Metrics Arrays**: When using `role_arn` authentication, ensure the assumed role has proper CloudWatch permissions
2. **Missing CPU/Memory Data**: Verify the cross-account role includes `cloudwatch:GetMetricStatistics` permission
3. **"Unable to assess service performance"**: This indicates missing metrics data, usually due to:
   - Insufficient IAM permissions on the assumed role
   - ECS service not publishing metrics to CloudWatch
   - Incorrect region configuration
   - Service hasn't been running long enough to generate metrics

**Solution for Role ARN Issues**:
- Ensure the cross-account IAM role has the `ECSMonitoringPolicy` attached
- Verify the role can be assumed with the correct `ExternalId: 'ecs-monitoring-app'`
- Check that ECS services have proper task definitions with CloudWatch logging enabled
- Wait 5-10 minutes after service deployment for metrics to appear in CloudWatch
- **Session Duration**: Cross-account role configured with 4-hour maximum session duration (14400 seconds) for extended monitoring operations

### Debug Mode
```bash
# Enable debug logging
LOG_LEVEL=DEBUG python app.py

# Check OAuth configuration
echo "COGNITO_REGION: $COGNITO_REGION"
echo "COGNITO_USER_POOL_ID: $COGNITO_USER_POOL_ID"
echo "COGNITO_CLIENT_ID: $COGNITO_CLIENT_ID"

# Test role assumption manually
aws sts assume-role --role-arn "arn:aws:iam::ACCOUNT:role/ECSMonitoringCrossAccountRole" \
  --role-session-name "test-session" --external-id "ecs-monitoring-app"

# Test CloudWatch permissions
aws cloudwatch get-metric-statistics --namespace AWS/ECS \
  --metric-name CPUUtilization --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-01-02T00:00:00Z --period 3600 --statistics Average \
  --dimensions Name=ServiceName,Value=your-service Name=ClusterName,Value=your-cluster
```

## 📈 Monitoring Metrics

The system tracks:
- Service CPU/Memory utilization
- Task health and count
- Error rates from logs
- Recommendation accuracy
- System performance metrics

---

## 🔄 Data Persistence

### Account Storage
- **Persistent**: Account credentials stored in DynamoDB with all authentication methods
- **Auto-load**: Existing accounts loaded on application startup
- **Refresh**: On-demand data refresh via UI button
- **Cache**: Cluster/service data cached for 24 hours
- **Authentication Support**: Stores access_key, secret_key, profile_name, role_arn, session_token

### Service Recommendation Storage
- **Individual Service Analysis**: Each service gets dedicated recommendation record
- **Health Status Tracking**: Monitor service health evolution over time
- **Scaling Action History**: Track recommended scaling actions per service
- **Priority-based Filtering**: Query services by priority level for focused attention
- **Auto-cleanup**: Recommendations auto-expire after 7 days

### Data Refresh Flow
1. Click "🔄 Refresh Data" button for any account
2. System fetches latest ECS cluster and service information
3. Updates cached data in DynamoDB
4. UI displays refreshed metrics and status

### Service Recommendation Workflow
1. Call `/cluster-recommendations/{account_id}` API endpoint
2. System processes each cluster and service individually
3. Generates AI recommendations using `get_service_specific_metrics`
4. Calls `generate_service_recommendations` for each service
5. Stores results in `ecs-service-recommendation` table with health/priority/scaling data
6. Returns comprehensive analysis with health summary

### AI Chat Flow
1. Get recommendations for account or service
2. Chat interface appears below recommendations
3. Ask questions about scaling, optimization, or technical scenarios
4. AI provides context-aware responses based on current infrastructure
5. Continue conversation for deeper technical guidance

---

**Built with ❤️ using FastAPI, AWS Bedrock Claude 3.5 Sonnet, and modern web technologies**

## 📊 Metrics Collected

### ECS Service Metrics
- **CPU Utilization**: Average and maximum percentages
- **Memory Utilization**: Average and maximum percentages
- **Task Counts**: Running vs desired task counts
- **Service Status**: Active, inactive, or error states
- **Task Definition Details**:
  - Family name and revision number
  - Compatibility modes (EC2/Fargate)
  - Required compatibilities configuration
  - Task-level CPU and memory specifications
  - Individual container resource allocations (CPU, memory, memoryReservation)

### Target Group Metrics (ALB Only)
- **Healthy Hosts**: Average and maximum healthy target counts
- **Unhealthy Hosts**: Average and maximum unhealthy target counts
- **Response Time**: Average and maximum response times (seconds)
- **Request Count**: Average and maximum requests per period
- **HTTP Status Codes**: 2XX (success), 3XX (redirect), 4XX (client error) counts
- **Error Percentage**: Calculated as (3XX + 4XX) / 2XX * 100 for service health assessment
- **Load Balancer Type**: Automatic detection (ALB supported, NLB ignored)

### AI-Enhanced Analysis
- **Performance Issues**: Severity-based issue detection
- **Scaling Recommendations**: CPU/Memory threshold-based suggestions
- **Cost Optimization**: Resource right-sizing recommendations
- **Target Group Health**: Load balancer performance analysis

### Email Notification Flow
1. Click "📧 Email Report" button for any account
2. Enter recipient email address
3. System generates comprehensive recommendation report
4. Professional HTML email sent via AWS SES
5. Email includes account details, health summary, and reference links

### Excel Report Generation
1. Click "📊 Excel Report" button for any account
2. System generates comprehensive Excel workbook
3. Each ECS cluster becomes a separate sheet tab
4. Each service row includes metrics and 5 AI recommendations
5. Auto-downloads file: `ECS_Report_AccountName_YYYYMMDD_HHMMSS.xlsx`

## 🎨 UI Improvements

### Collapsible Cluster View
- **Organized Display**: Clusters are now collapsible to reduce visual clutter
- **Cluster Statistics**: Each cluster header shows summary stats (services, tasks, CPU, memory)
- **Individual Toggle**: Click any cluster header to expand/collapse its services
- **Bulk Controls**: "Expand All" and "Collapse All" buttons for quick navigation
- **Improved Navigation**: Better organization for accounts with many clusters and services

### Enhanced User Experience
- **Clean Interface**: Services are hidden by default, showing only cluster summaries
- **Quick Overview**: Cluster stats provide immediate insights without expanding
- **Flexible Viewing**: Users can focus on specific clusters while keeping others collapsed
- **Responsive Design**: Maintains mobile-friendly layout with improved organization

## 🔐 **User Authentication Display**
- **User Information**: Displays authenticated user's name and email in dashboard header
- **Real-time Loading**: User info loaded automatically on dashboard access
- **Secure Display**: Shows current authenticated user from Cognito JWT token
- **Responsive Design**: User info panel adapts to different screen sizes
- **Visual Integration**: Styled user info box matches dashboard theme

## 📝 Recent Updates

### Best Practices Implementation (v1.0.0)
- **Open Source Ready**: Added MIT License, SECURITY.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md
- **CI/CD Pipeline**: GitHub Actions for automated testing and Docker builds
- **Code Quality**: Pre-commit hooks with Black, isort, Flake8
- **API Documentation**: Enhanced OpenAPI/Swagger docs at `/api/docs`
- **Rate Limiting**: 100 req/min for read, 10 req/min for write operations
- **Health Monitoring**: Comprehensive component-level health checks
- **Development Tools**: requirements-dev.txt with pytest, mypy, black, flake8

### Bug Fixes
- **ECS Service Batching**: Fixed AWS ECS `describe_services` API limitation by implementing batching to process services in groups of 10 (AWS maximum limit)
- **Large Cluster Support**: Improved handling of clusters with more than 10 services to prevent `InvalidParameterException`
- **Environment Variables**: Added `python-dotenv` package to automatically load `.env` file on startup
- **Lifespan Events**: Converted deprecated `@app.on_event("startup")` to modern `lifespan` context manager
- **Centralized Logging**: Implemented unified logging configuration across all modules with consistent formatting

### Logging Configuration
- **Centralized Logging**: All modules use `logger_config.py` for consistent log formatting
- **Log Format**: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Log Levels**: Configurable via `LOG_LEVEL` environment variable (DEBUG, INFO, WARNING, ERROR)
- **No Print Statements**: All print statements replaced with proper logging calls

### Configuration Updates
- **Centralized Config**: All hardcoded values moved to `config.py` with environment variable support
- **Low Priority Constants**: AWS namespaces, metric names, and JWT algorithm now configurable
- **AWS Namespaces**: `ECS_NAMESPACE` (default: AWS/ECS), `ALB_NAMESPACE` (default: AWS/ApplicationELB)
- **Metric Names**: All CloudWatch metric names configurable (CPUUtilization, MemoryUtilization, etc.)
- **JWT Algorithm**: Configurable JWT verification algorithm (default: ES256)

### Logging Configuration
- **Log Level**: Set to INFO and ERROR only for cleaner production logs
- **Format**: Timestamp, logger name, level, and message
- **Debug Mode**: Use `LOG_LEVEL=DEBUG` environment variable for detailed debugging
