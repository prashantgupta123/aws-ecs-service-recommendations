import asyncio
import io
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import pandas as pd
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ai_recommender import AIRecommender
from auth import get_current_user
from config import Config
from ecs_monitor import ECSMonitor
from knowledge_db import KnowledgeDB
from logger_config import setup_logger

logger = setup_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global instances
ai_recommenders: Dict[str, AIRecommender] = {}
knowledge_db = KnowledgeDB(Config.AWS_DEFAULT_REGION)
chat_history: Dict[str, List[Dict]] = {}  # Store chat history per account
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Loading existing accounts...")
    accounts = await knowledge_db.get_all_accounts()

    for account in accounts:
        try:
            ai_recommenders[account["account_id"]] = AIRecommender(
                Config.AWS_DEFAULT_REGION
            )
            logger.info(
                f"Loaded account: {account['account_name']} ({account['account_id']})"
            )
        except Exception as e:
            logger.error(f"Error loading account {account['account_id']}: {e}")

    daily_enabled = Config.DAILY_RECOMMENDATIONS_CRON_ENABLED
    weekly_enabled = Config.WEEKLY_RECOMMENDATIONS_CRON_ENABLED

    if daily_enabled:
        scheduler.add_job(
            generate_daily_cluster_recommendations,
            CronTrigger(
                hour=Config.DAILY_RECOMMENDATIONS_HOUR,
                minute=Config.DAILY_RECOMMENDATIONS_MINUTE,
            ),
            id="daily_cluster_recommendations",
        )
        scheduler.add_job(
            send_daily_high_priority_reports,
            CronTrigger(
                hour=Config.DAILY_REPORTS_HOUR, minute=Config.DAILY_REPORTS_MINUTE
            ),
            id="daily_high_priority_reports",
        )
        logger.info(
            "Daily schedulers enabled: Cluster recommendations (7:00 AM), High-priority reports (9:00 AM)"
        )
    else:
        logger.info(
            "Daily schedulers disabled via DAILY_RECOMMENDATIONS_CRON_ENABLED=false"
        )

    if weekly_enabled:
        scheduler.add_job(
            generate_weekly_cluster_recommendations,
            CronTrigger(
                day_of_week="mon",
                hour=Config.WEEKLY_RECOMMENDATIONS_HOUR,
                minute=Config.WEEKLY_RECOMMENDATIONS_MINUTE,
            ),
            id="weekly_cluster_recommendations",
        )
        scheduler.add_job(
            send_weekly_comprehensive_reports,
            CronTrigger(
                day_of_week="mon",
                hour=Config.WEEKLY_REPORTS_HOUR,
                minute=Config.WEEKLY_REPORTS_MINUTE,
            ),
            id="weekly_comprehensive_reports",
        )
        logger.info(
            "Weekly schedulers enabled: Cluster recommendations (Monday 8:00 AM), Comprehensive reports (Monday 10:00 AM)"
        )
    else:
        logger.info(
            "Weekly schedulers disabled via WEEKLY_RECOMMENDATIONS_CRON_ENABLED=false"
        )

    if daily_enabled or weekly_enabled:
        scheduler.start()
        logger.info("Scheduler started successfully")
    else:
        logger.info("No cron jobs enabled, scheduler not started")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown()


app = FastAPI(
    title="ECS Monitoring & AI Recommendations",
    description="""
    🏗️ **ECS Monitoring & AI Recommendations System**

    A comprehensive web application that monitors AWS ECS infrastructure across
    multiple accounts and provides AI-powered recommendations using AWS Bedrock Claude Sonnet 4.

    ## Features
    - Multi-account ECS monitoring
    - AI-powered recommendations
    - Real-time metrics collection
    - Automated email reports
    - Interactive dashboards

    ## Authentication
    - Cognito JWT token validation
    - Optional authentication bypass for local development

    ## Rate Limits
    - 100 requests per minute per IP
    - 1000 requests per hour per IP
    """,
    version="1.0.0",
    contact={
        "name": "Prashant Gupta",
        "email": "prashantgupta036@gmail.com",
        "url": "https://github.com/prashantgupta123/aws-ecs-service-recommendations",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def get_monitor(account_id: str) -> ECSMonitor:
    """Get or create ECS monitor for account at runtime"""
    # Get account details from knowledge base
    accounts = await knowledge_db.get_all_accounts()
    account_info = next(
        (acc for acc in accounts if acc["account_id"] == account_id), None
    )

    if not account_info:
        raise HTTPException(404, "Account not found")

    # Always create fresh monitor instance to avoid session token expiration
    monitor = ECSMonitor(
        region=account_info["region"],
        access_key=account_info.get("access_key", ""),
        secret_key=account_info.get("secret_key", ""),
        profile_name=account_info.get("profile_name", ""),
        role_arn=account_info.get("role_arn", ""),
        session_token=account_info.get("session_token", ""),
    )

    return monitor


class AWSAccount(BaseModel):
    account_id: str
    account_name: str
    region: str = Config.AWS_DEFAULT_REGION
    access_key: Optional[str] = ""
    secret_key: Optional[str] = ""
    profile_name: Optional[str] = ""
    role_arn: Optional[str] = ""
    session_token: Optional[str] = ""


class MonitoringStatus(BaseModel):
    account_id: str
    status: str
    clusters: List[str]
    last_updated: str


class EmailNotification(BaseModel):
    email: str
    account_id: str


@app.get("/user-info")
async def get_user_info(user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "name": user.get("name", user.get("given_name", "Unknown User")),
        "email": user.get("email", "unknown@example.com"),
        "authenticated": True,
    }


@app.get("/", response_class=HTMLResponse)
async def analytics_dashboard(request: Request, user: dict = Depends(get_current_user)):
    try:
        logger.info(
            f"Analytics dashboard accessed by user: {user.get('email', 'unknown')}"
        )
        with open("analytics_dashboard.html", "r") as f:
            return f.read()
    except HTTPException as e:
        logger.error(f"Dashboard authentication error: {e}")
        # Return a simple login page or redirect to OAuth
        return HTMLResponse(
            """
        <html>
            <head><title>Authentication Required</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>🔐 Authentication Required</h2>
                <p>Please authenticate to access the ECS Monitoring Dashboard.</p>
                <p><a href="/debug/oauth-test" style="color: #007bff;">Debug OAuth</a> |
                   <a href="/debug/headers" style="color: #007bff;">Debug Headers</a></p>
            </body>
        </html>
        """,
            status_code=401,
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return HTMLResponse(
            f"""
        <html>
            <head><title>Dashboard Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>❌ Dashboard Error</h2>
                <p>Error loading dashboard: {str(e)}</p>
                <p><a href="/debug/simple" style="color: #007bff;">Test Simple Endpoint</a></p>
            </body>
        </html>
        """,
            status_code=500,
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/oauth2/idpresponse")
async def oauth_callback(request: Request):
    """Handle OAuth callback from Cognito - ALB processes the code automatically"""
    try:
        logger.info(f"OAuth callback received")
        logger.info(f"URL: {request.url}")
        logger.info(f"Query params: {dict(request.query_params)}")
        logger.info(f"Headers: {dict(request.headers)}")

        # Check for error parameters
        error = request.query_params.get("error")
        if error:
            error_description = request.query_params.get(
                "error_description", "Unknown error"
            )
            logger.error(f"OAuth error: {error} - {error_description}")
            return HTMLResponse(
                f"""
            <html>
                <head><title>Authentication Error</title></head>
                <body>
                    <h2>Authentication Error</h2>
                    <p>Error: {error}</p>
                    <p>Description: {error_description}</p>
                    <p><a href="/">Return to Dashboard</a></p>
                </body>
            </html>
            """,
                status_code=400,
            )

        # Log successful callback
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        logger.info(
            f"OAuth callback successful - Code: {code[:10] if code else 'None'}..., State: {state[:10] if state else 'None'}..."
        )

        # Return simple HTML with JavaScript redirect to avoid meta refresh issues
        return HTMLResponse(
            """
        <html>
            <head>
                <title>Authentication Complete</title>
                <script>
                    setTimeout(function() {
                        window.location.href = '/';
                    }, 1000);
                </script>
            </head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>✅ Authentication Successful</h2>
                <p>Redirecting to dashboard...</p>
                <p><a href="/" style="color: #007bff; text-decoration: none;">Click here if not redirected automatically</a></p>
            </body>
        </html>
        """
        )

    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        return HTMLResponse(
            f"""
        <html>
            <head><title>Authentication Error</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2>❌ Authentication Error</h2>
                <p>An error occurred during authentication: {str(e)}</p>
                <p><a href="/" style="color: #007bff; text-decoration: none;">Return to Dashboard</a></p>
                <details style="margin-top: 20px; text-align: left; max-width: 600px; margin-left: auto; margin-right: auto;">
                    <summary>Technical Details</summary>
                    <pre style="background: #f8f9fa; padding: 10px; border-radius: 5px; overflow-x: auto;">{str(e)}</pre>
                </details>
            </body>
        </html>
        """,
            status_code=500,
        )


@app.get("/debug/headers")
async def debug_headers(request: Request):
    """Debug endpoint to check headers - NO AUTH REQUIRED"""
    logger.info(f"Debug headers called: {dict(request.headers)}")
    return {
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers),
        "cognito_token": request.headers.get("x-amzn-oidc-data", "Not found"),
        "query_params": dict(request.query_params),
        "path_params": dict(request.path_params)
        if hasattr(request, "path_params")
        else {},
        "client": str(request.client) if hasattr(request, "client") else "Unknown",
    }


@app.get("/debug/simple")
async def debug_simple():
    """Simple debug endpoint"""
    return {
        "status": "ok",
        "message": "Simple endpoint working",
        "timestamp": datetime.now().isoformat(),
        "environment": {
            "cognito_region": Config.COGNITO_REGION or "Not set",
            "cognito_user_pool_id": Config.COGNITO_USER_POOL_ID or "Not set",
            "cognito_client_id": Config.COGNITO_CLIENT_ID[:10] + "..."
            if Config.COGNITO_CLIENT_ID
            else "Not set",
        },
    }


@app.get("/debug/oauth-test")
async def debug_oauth_test(request: Request):
    """Test OAuth callback handling without authentication"""
    try:
        from auth import verify_cognito_token

        # Test token verification
        user = verify_cognito_token(request)

        return {
            "status": "success",
            "url": str(request.url),
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "user_verified": user is not None,
            "user_email": user.get("email") if user else None,
            "cognito_token_present": "x-amzn-oidc-data" in request.headers,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"OAuth test error: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "url": str(request.url),
            "headers": dict(request.headers),
            "query_params": dict(request.query_params),
            "timestamp": datetime.now().isoformat(),
        }


@app.get("/add-account", response_class=HTMLResponse)
async def add_account_page(request: Request, user: dict = Depends(get_current_user)):
    """Add account page"""
    with open("add_account.html", "r") as f:
        return f.read()


@app.get("/recommendations-dashboard", response_class=HTMLResponse)
async def recommendations_dashboard(
    request: Request, user: dict = Depends(get_current_user)
):
    """Recommendations dashboard page"""
    with open("recommendations_dashboard.html", "r") as f:
        return f.read()


@app.get("/services-dashboard", response_class=HTMLResponse)
async def services_dashboard(request: Request, user: dict = Depends(get_current_user)):
    """Services dashboard page"""
    with open("dashboard.html", "r") as f:
        return f.read()


@app.get("/services-dashboard-optimized", response_class=HTMLResponse)
async def services_dashboard_optimized(
    request: Request, user: dict = Depends(get_current_user)
):
    """Optimized services dashboard page with pagination and filtering"""
    with open("dashboard_optimized_fixed.html", "r") as f:
        return f.read()


@app.get("/dashboard-comparison", response_class=HTMLResponse)
async def dashboard_comparison(
    request: Request, user: dict = Depends(get_current_user)
):
    """Dashboard comparison page"""
    with open("dashboard_comparison.html", "r") as f:
        return f.read()


@app.get("/cluster-dashboard", response_class=HTMLResponse)
async def cluster_dashboard(request: Request, user: dict = Depends(get_current_user)):
    """Cluster dashboard page"""
    with open("cluster_dashboard.html", "r") as f:
        return f.read()


@app.get("/all-recommendations")
async def get_all_recommendations():
    """Get all service recommendations grouped by priority and health"""
    try:
        accounts = await knowledge_db.get_all_accounts()
        all_recommendations = []

        for account in accounts:
            account_id = account["account_id"]
            recommendations = await knowledge_db.get_service_recommendations_by_health(
                account_id
            )

            for rec in recommendations:
                rec["account_name"] = account["account_name"]
                all_recommendations.append(rec)

        # Group by priority then by service_health
        grouped = {}
        for rec in all_recommendations:
            priority = rec.get("priority", "medium")
            health = rec.get("service_health", "unknown")

            if priority not in grouped:
                grouped[priority] = {}
            if health not in grouped[priority]:
                grouped[priority][health] = []

            grouped[priority][health].append(rec)

        # Sort priorities: high, medium, low
        priority_order = ["high", "medium", "low"]
        health_order = ["critical", "warning", "error", "good"]

        sorted_grouped = {}
        for priority in priority_order:
            if priority in grouped:
                sorted_grouped[priority] = {}
                for health in health_order:
                    if health in grouped[priority]:
                        sorted_grouped[priority][health] = grouped[priority][health]

        return sorted_grouped
    except Exception as e:
        return {"error": str(e)}


@app.get("/analytics-data")
async def get_analytics_data():
    """Get comprehensive analytics data from both knowledge base tables"""
    try:
        # Get all accounts with their cluster data
        accounts = await knowledge_db.get_all_accounts()
        analytics_data = {
            "accounts": [],
            "total_accounts": len(accounts),
            "active_accounts": 0,
            "total_clusters": 0,
            "total_services": 0,
            "total_tasks": 0,
            "recommendations_summary": {
                "total": 0,
                "by_priority": {"high": 0, "medium": 0, "low": 0},
                "by_health": {"good": 0, "warning": 0, "critical": 0, "error": 0},
                "by_scaling": {"scale_up": 0, "scale_down": 0, "no_change": 0},
            },
            "recent_recommendations": [],
        }

        all_recommendations = []

        for account in accounts:
            account_id = account["account_id"]

            # Get cluster data from CLUSTER_DATA
            cluster_data = await knowledge_db.get_cluster_data(account_id)

            # Calculate account statistics
            account_clusters = len(cluster_data) if cluster_data else 0
            account_services = 0
            account_tasks = 0

            if cluster_data:
                for cluster_name, services in cluster_data.items():
                    account_services += len(services)
                    for service in services:
                        account_tasks += service.get("running_count", 0)

            # Determine account status (active if it has cluster data)
            account_status = "active" if cluster_data else "inactive"
            if account_status == "active":
                analytics_data["active_accounts"] += 1

            analytics_data["total_clusters"] += account_clusters
            analytics_data["total_services"] += account_services
            analytics_data["total_tasks"] += account_tasks

            # Add account info
            analytics_data["accounts"].append(
                {
                    "account_id": account_id,
                    "account_name": account["account_name"],
                    "region": account.get("region", "N/A"),
                    "status": account_status,
                    "clusters": account_clusters,
                    "services": account_services,
                    "tasks": account_tasks,
                    "last_updated": account.get("last_updated", "Never"),
                }
            )

            # Get service recommendations from ecs-service-recommendation table
            recommendations = await knowledge_db.get_service_recommendations_by_health(
                account_id
            )

            for rec in recommendations:
                rec["account_name"] = account["account_name"]
                all_recommendations.append(rec)

                # Update counters
                analytics_data["recommendations_summary"]["total"] += 1

                priority = rec.get("priority", "medium")
                health = rec.get("service_health", "unknown")
                scaling = rec.get("scaling_action", "no_change")

                if priority in analytics_data["recommendations_summary"]["by_priority"]:
                    analytics_data["recommendations_summary"]["by_priority"][
                        priority
                    ] += 1

                if health in analytics_data["recommendations_summary"]["by_health"]:
                    analytics_data["recommendations_summary"]["by_health"][health] += 1

                if scaling in analytics_data["recommendations_summary"]["by_scaling"]:
                    analytics_data["recommendations_summary"]["by_scaling"][
                        scaling
                    ] += 1

        # Sort recommendations by priority and timestamp for recent recommendations
        priority_order = {"high": 3, "medium": 2, "low": 1}
        all_recommendations.sort(
            key=lambda x: (
                priority_order.get(x.get("priority", "medium"), 2),
                x.get("timestamp", ""),
            ),
            reverse=True,
        )

        # Get top 50 recent recommendations
        analytics_data["recent_recommendations"] = all_recommendations[:50]

        return analytics_data

    except Exception as e:
        logger.error(f"Error getting analytics data: {e}")
        return {"error": str(e)}


@app.post(
    "/accounts",
    tags=["Accounts"],
    summary="Add AWS account for monitoring",
    response_description="Account added successfully",
)
@limiter.limit("10/minute")
async def add_account(
    request: Request, account: AWSAccount, background_tasks: BackgroundTasks
):
    """Add AWS account for monitoring.

    Args:
        request: FastAPI request object
        account: AWS account details
        background_tasks: Background task manager

    Returns:
        dict: Status message
    """
    # Create AI recommender
    ai_recommenders[account.account_id] = AIRecommender(Config.AWS_DEFAULT_REGION)

    # Store account in knowledge database
    await knowledge_db.store_account(
        {
            "account_id": account.account_id,
            "account_name": account.account_name,
            "access_key": account.access_key or "",
            "secret_key": account.secret_key or "",
            "profile_name": account.profile_name or "",
            "role_arn": account.role_arn or "",
            "session_token": account.session_token or "",
            "region": account.region,
        }
    )

    # background_tasks.add_task(start_monitoring, account.account_id)
    return {"status": "Account added, monitoring started"}


@app.get(
    "/accounts",
    tags=["Accounts"],
    summary="List all monitored accounts",
    response_description="List of accounts with status",
)
@limiter.limit("100/minute")
async def get_accounts(
    request: Request,
    page: int = 1,
    limit: int = 10,
    search: str = "",
    status_filter: str = "",
):
    """Get accounts with optional pagination and filtering.

    Args:
        request: FastAPI request object
        page: Page number (default: 1)
        limit: Items per page (default: 10)
        search: Search by account name or ID
        status_filter: Filter by status (active/inactive)

    Returns:
        dict: Accounts list with pagination info
    """
    stored_accounts = await knowledge_db.get_all_accounts()
    statuses = []

    for account in stored_accounts:
        account_id = account["account_id"]

        try:
            monitor = await get_monitor(account_id)
            status = await monitor.get_status()
            # Get cached cluster data first
            cluster_details = await knowledge_db.get_cluster_data(account_id)

            # If no cached data, get fresh data
            if not cluster_details:
                cluster_details = await monitor.get_cluster_details()
                await knowledge_db.store_cluster_data(account_id, cluster_details)

            statuses.append(
                {
                    "account_id": account_id,
                    "account_name": account["account_name"],
                    "status": status["status"],
                    "clusters": status["clusters"],
                    "cluster_details": cluster_details,
                    "last_updated": status["last_updated"],
                }
            )
        except Exception as e:
            # Account has issues, mark as inactive
            statuses.append(
                {
                    "account_id": account_id,
                    "account_name": account["account_name"],
                    "status": "inactive",
                    "clusters": [],
                    "cluster_details": {},
                    "last_updated": "error",
                }
            )

    # Apply filters
    if search:
        search_lower = search.lower()
        statuses = [
            acc
            for acc in statuses
            if search_lower in acc["account_name"].lower()
            or search_lower in acc["account_id"].lower()
        ]

    if status_filter:
        statuses = [acc for acc in statuses if acc["status"] == status_filter]

    # For backward compatibility, return all if no pagination params
    if page == 1 and limit == 10 and not search and not status_filter:
        return statuses

    # Apply pagination
    total_count = len(statuses)
    start_index = (page - 1) * limit
    end_index = start_index + limit
    paginated_statuses = statuses[start_index:end_index]

    return {
        "accounts": paginated_statuses,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": (total_count + limit - 1) // limit,
            "has_next": end_index < total_count,
            "has_prev": page > 1,
        },
        "filters": {"search": search, "status_filter": status_filter},
    }


@app.get("/recommendations/{account_id}")
async def get_recommendations(account_id: str):
    monitor = await get_monitor(account_id)
    ai_recommender = ai_recommenders.get(
        account_id, AIRecommender(Config.AWS_DEFAULT_REGION)
    )

    logger.debug(f"AI Recommender bedrock client: {ai_recommender.bedrock is not None}")
    logger.debug(f"AI Recommender model_id: {ai_recommender.model_id}")

    try:
        await monitor.monitor_clusters()

        metrics = await monitor.get_cluster_metrics()
        logs = await monitor.get_recent_logs()

        logger.debug(f"Metrics data: {json.dumps(metrics, indent=2)[:500]}...")
        logger.debug(
            f"Logs data: {list(logs.keys())} clusters with {sum(len(v) for v in logs.values())} total log entries"
        )

        recommendations = await ai_recommender.generate_recommendations(metrics, logs)
        logger.debug(
            f"Generated recommendations: {json.dumps(recommendations, indent=2)}"
        )

        await knowledge_db.store_recommendations(account_id, recommendations)

        # Add recommendations to chat history
        if account_id not in chat_history:
            chat_history[account_id] = []

        # Clear previous chat and add new context
        chat_history[account_id] = []

        # Add system context
        context_msg = f"You are an AWS ECS expert assistant. We are discussing account-wide ECS recommendations for account {account_id}."
        chat_history[account_id].append(
            {"role": "system", "content": [{"text": context_msg}]}
        )

        # Add recommendations as assistant message
        rec_msg = f"I have analyzed your ECS infrastructure and provided these account-wide recommendations: {json.dumps(recommendations, indent=2)}"
        chat_history[account_id].append(
            {"role": "assistant", "content": [{"text": rec_msg}]}
        )

        return recommendations
    except Exception as e:
        logger.error(f"Error getting recommendations for {account_id}: {e}")
        return {
            "error": str(e),
            "fallback": "Basic monitoring active, AI recommendations unavailable",
        }


@app.get("/export-excel/{account_id}")
async def export_excel_report(account_id: str):
    """Generate Excel report with cluster sheets, service metrics, and recommendations"""
    try:
        monitor = await get_monitor(account_id)
        ai_recommender = ai_recommenders.get(
            account_id, AIRecommender(Config.AWS_DEFAULT_REGION)
        )

        # Get fresh data
        await monitor.monitor_clusters()
        cluster_details = await monitor.get_cluster_details()

        # Create Excel workbook
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            for cluster_name, services in cluster_details.items():
                # Create sheet for each cluster
                sheet_data = []

                for service in services:
                    # Get service-specific metrics and recommendations
                    service_metrics = await monitor.get_service_specific_metrics(
                        cluster_name, service["name"]
                    )
                    service_logs = await monitor.get_service_logs(
                        cluster_name, service["name"]
                    )

                    # Generate AI recommendations for this service
                    from ai_recommender_service import generate_service_recommendations

                    bedrock_client = ai_recommender.bedrock if ai_recommender else None
                    model_id = ai_recommender.model_id if ai_recommender else None

                    try:
                        service_recs = await generate_service_recommendations(
                            bedrock_client,
                            model_id,
                            service_metrics,
                            service_logs,
                            cluster_name,
                            service["name"],
                        )
                    except:
                        service_recs = {
                            "recommendations": ["AI recommendations unavailable"]
                        }

                    # Calculate target group metrics summary
                    tg_summary = ""
                    if service.get("target_groups"):
                        tg_details = []
                        for tg_name, tg_data in service["target_groups"].items():
                            tg_details.append(
                                f"{tg_name}: {tg_data.get('healthy_hosts_avg', 0)} healthy hosts, {tg_data.get('response_time_avg', 0):.3f}s response"
                            )
                        tg_summary = "; ".join(tg_details)

                    # Get top 5 recommendations
                    recommendations = service_recs.get("recommendations", [])
                    if isinstance(recommendations, list):
                        top_5_recs = recommendations[:5]
                    else:
                        top_5_recs = ["No specific recommendations"]

                    sheet_data.append(
                        {
                            "Service Name": service["name"],
                            "Status": service["status"],
                            "Running Tasks": service["running_count"],
                            "Desired Tasks": service["desired_count"],
                            "CPU Average (%)": service.get("cpu_avg", "N/A"),
                            "CPU Maximum (%)": service.get("cpu_max", "N/A"),
                            "Memory Average (%)": service.get("memory_avg", "N/A"),
                            "Memory Maximum (%)": service.get("memory_max", "N/A"),
                            "Target Groups": tg_summary,
                            "Health Status": service_recs.get(
                                "service_health", "Unknown"
                            ),
                            "Scaling Action": service_recs.get(
                                "scaling_action", "no_change"
                            ),
                            "Priority": service_recs.get("priority", "medium"),
                            "Recommendation 1": top_5_recs[0]
                            if len(top_5_recs) > 0
                            else "",
                            "Recommendation 2": top_5_recs[1]
                            if len(top_5_recs) > 1
                            else "",
                            "Recommendation 3": top_5_recs[2]
                            if len(top_5_recs) > 2
                            else "",
                            "Recommendation 4": top_5_recs[3]
                            if len(top_5_recs) > 3
                            else "",
                            "Recommendation 5": top_5_recs[4]
                            if len(top_5_recs) > 4
                            else "",
                        }
                    )

                # Create DataFrame and write to sheet
                if sheet_data:
                    df = pd.DataFrame(sheet_data)
                    # Clean cluster name for sheet name (Excel sheet names have restrictions)
                    clean_cluster_name = cluster_name.replace("/", "_").replace(
                        "\\", "_"
                    )[:31]
                    df.to_excel(writer, sheet_name=clean_cluster_name, index=False)

                    # Auto-adjust column widths
                    worksheet = writer.sheets[clean_cluster_name]
                    for i, col in enumerate(df.columns):
                        max_len = max(df[col].astype(str).map(len).max(), len(col))
                        worksheet.set_column(i, i, min(max_len + 2, 50))

        output.seek(0)

        # Get account name for filename
        accounts = await knowledge_db.get_all_accounts()
        account_info = next(
            (acc for acc in accounts if acc["account_id"] == account_id), None
        )
        account_name = account_info["account_name"] if account_info else account_id

        filename = (
            f"ECS_Report_{account_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except Exception as e:
        logger.error(f"Error generating Excel report: {e}")
        raise HTTPException(500, f"Error generating report: {str(e)}")


@app.post("/send-email/{account_id}")
async def send_email_notification(account_id: str, email_request: EmailNotification):
    """Send email notification with account-wide recommendations"""
    try:
        # Get account details
        accounts = await knowledge_db.get_all_accounts()
        account_info = next(
            (acc for acc in accounts if acc["account_id"] == account_id), None
        )
        if not account_info:
            raise HTTPException(404, "Account info not found")

        # Get recommendations from knowledge base
        recommendations = await knowledge_db.get_current_recommendations(account_id)

        if not recommendations:
            # If no stored recommendations, generate new ones
            monitor = await get_monitor(account_id)
            ai_recommender = ai_recommenders.get(
                account_id, AIRecommender(Config.AWS_DEFAULT_REGION)
            )

            metrics = await monitor.get_cluster_metrics()
            logs = await monitor.get_recent_logs()
            recommendations = await ai_recommender.generate_recommendations(
                metrics, logs
            )
            await knowledge_db.store_recommendations(account_id, recommendations)

        # Send email
        await send_recommendations_email(
            email_request.email, account_info, recommendations
        )

        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {"error": str(e)}


async def send_recommendations_email(
    email: str, account_info: Dict, recommendations: Dict
):
    """Send formatted email with recommendations"""
    try:
        ses_client = boto3.client("ses")

        # Format recommendations
        health_status = recommendations.get("overall_health", "Unknown")
        summary = recommendations.get("summary", "No summary available")

        # Build detailed recommendations
        detailed_recs = []

        # Add debug info to see what's in recommendations
        logger.debug(
            f"DEBUG EMAIL: Recommendations keys: {list(recommendations.keys())}"
        )
        logger.debug(
            f"DEBUG EMAIL: Scaling recs count: {len(recommendations.get('scaling_recommendations', []))}"
        )
        logger.debug(
            f"DEBUG EMAIL: Performance issues count: {len(recommendations.get('performance_issues', []))}"
        )
        logger.debug(
            f"DEBUG EMAIL: Cost optimization count: {len(recommendations.get('cost_optimization', []))}"
        )

        # Scaling Recommendations
        if (
            recommendations.get("scaling_recommendations")
            and len(recommendations["scaling_recommendations"]) > 0
        ):
            detailed_recs.append("<h4>🔄 Scaling Recommendations:</h4>")
            for i, rec in enumerate(recommendations["scaling_recommendations"]):
                logger.debug(f"DEBUG EMAIL: Processing scaling rec {i}: {rec}")
                action_color = {
                    "scale_up": "#dc3545",
                    "scale_down": "#28a745",
                    "no_change": "#6c757d",
                }.get(rec.get("action", "no_change"), "#6c757d")
                detailed_recs.append(
                    f"<div style='margin: 5px 0; padding: 8px; background: #f8f9fa; border-left: 4px solid {action_color}; border-radius: 3px;'>"
                )
                detailed_recs.append(
                    f"<strong style='color: #333; font-size: 1.1em;'>{rec.get('service', 'Unknown Service')} ({rec.get('cluster', 'Unknown Cluster')})</strong>"
                )
                detailed_recs.append(
                    f"<br><span style='color: {action_color}; font-weight: bold; text-transform: uppercase;'>{rec.get('action', 'No Action').replace('_', ' ')}</span>"
                )
                detailed_recs.append(
                    f"<br><em style='color: #666;'>{rec.get('reason', 'No reason provided')}</em>"
                )
                if rec.get("suggested_capacity"):
                    cap = rec["suggested_capacity"]
                    detailed_recs.append(
                        f"<br><div style='margin-top: 4px; padding: 4px; background: #e9ecef; border-radius: 2px;'>"
                    )
                    detailed_recs.append(
                        f"<small><strong>Suggested Capacity:</strong> CPU: {cap.get('cpu', 'N/A')}, Memory: {cap.get('memory', 'N/A')}, Tasks: {cap.get('desired_count', 'N/A')}</small>"
                    )
                    detailed_recs.append("</div>")
                detailed_recs.append("</div>")
        else:
            detailed_recs.append("<h4>🔄 Scaling Recommendations:</h4>")
            detailed_recs.append(
                "<p style='color: #666; font-style: italic;'>No scaling recommendations at this time.</p>"
            )

        # Performance Issues
        if (
            recommendations.get("performance_issues")
            and len(recommendations["performance_issues"]) > 0
        ):
            detailed_recs.append("<h4>⚠️ Performance Issues:</h4>")
            for i, issue in enumerate(recommendations["performance_issues"]):
                logger.debug(f"DEBUG EMAIL: Processing performance issue {i}: {issue}")
                severity_color = {
                    "high": "#dc3545",
                    "medium": "#ffc107",
                    "low": "#28a745",
                }.get(issue.get("severity", "medium"), "#ffc107")
                detailed_recs.append(
                    f"<div style='margin: 5px 0; padding: 8px; background: #f8f9fa; border-left: 4px solid {severity_color}; border-radius: 3px;'>"
                )
                detailed_recs.append(
                    f"<strong style='color: #333; font-size: 1.1em;'>{issue.get('service', 'Unknown Service')} ({issue.get('cluster', 'Unknown Cluster')})</strong>"
                )
                detailed_recs.append(
                    f"<br><span style='color: {severity_color}; font-weight: bold;'>{issue.get('severity', 'medium').upper()} SEVERITY</span>"
                )
                detailed_recs.append(
                    f"<br><strong>Issue:</strong> {issue.get('issue', 'No issue description')}"
                )
                detailed_recs.append(
                    f"<br><strong>Solution:</strong> <em style='color: #666;'>{issue.get('solution', 'No solution provided')}</em>"
                )
                detailed_recs.append("</div>")
        else:
            detailed_recs.append("<h4>⚠️ Performance Issues:</h4>")
            detailed_recs.append(
                "<p style='color: #666; font-style: italic;'>No performance issues detected.</p>"
            )

        # Cost Optimization
        if (
            recommendations.get("cost_optimization")
            and len(recommendations["cost_optimization"]) > 0
        ):
            detailed_recs.append("<h4>💰 Cost Optimization:</h4>")
            for i, cost_rec in enumerate(recommendations["cost_optimization"]):
                logger.debug(
                    f"DEBUG EMAIL: Processing cost optimization {i}: {cost_rec}"
                )
                detailed_recs.append(
                    f"<div style='margin: 10px 0; padding: 15px; background: #e8f5e8; border-left: 4px solid #28a745; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>"
                )
                detailed_recs.append(
                    f"<strong style='color: #333; font-size: 1.1em;'>Cluster: {cost_rec.get('cluster', 'Unknown Cluster')}</strong>"
                )
                detailed_recs.append(
                    f"<br>{cost_rec.get('recommendation', 'No recommendation available')}"
                )
                if cost_rec.get("potential_savings"):
                    detailed_recs.append(
                        f"<br><div style='margin-top: 8px; padding: 8px; background: #d4edda; border-radius: 3px;'>"
                    )
                    detailed_recs.append(
                        f"<small><strong>Potential Savings:</strong> <span style='color: #28a745; font-weight: bold;'>{cost_rec['potential_savings']}</span></small>"
                    )
                    detailed_recs.append("</div>")
                detailed_recs.append("</div>")
        else:
            detailed_recs.append("<h4>💰 Cost Optimization:</h4>")
            detailed_recs.append(
                "<p style='color: #666; font-style: italic;'>No cost optimization opportunities identified.</p>"
            )

        # Add raw recommendations for debugging
        if (
            not detailed_recs
            or len([r for r in detailed_recs if not r.startswith("<h4>")]) == 0
        ):
            detailed_recs.append("<h4>🔍 Debug Information:</h4>")
            detailed_recs.append(
                f"<pre style='background: #f8f9fa; padding: 10px; border-radius: 5px; font-size: 12px; overflow-x: auto;'>{json.dumps(recommendations, indent=2)}</pre>"
            )

        # Create HTML email template
        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .section {{ margin-bottom: 20px; padding: 15px; border-left: 4px solid #667eea; background: #f8f9fa; }}
                .health-good {{ color: #28a745; }}
                .health-warning {{ color: #ffc107; }}
                .health-critical {{ color: #dc3545; }}
                .recommendations {{ background: white; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .links {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                .links a {{ color: #1976d2; text-decoration: none; margin-right: 15px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🏗️ ECS Infrastructure Recommendations</h1>
                <p>AI-Powered Container Orchestration Analysis</p>
            </div>

            <div class="content">
                <div class="section">
                    <h3>Account Information</h3>
                    <p><strong>Account ID:</strong> {account_info['account_id']}</p>
                    <p><strong>Account Name:</strong> {account_info['account_name']}</p>
                    <p><strong>Region:</strong> {account_info['region']}</p>
                    <p><strong>Analysis Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                </div>

                <div class="section">
                    <h3>Overall Health Summary</h3>
                    <p class="health-{health_status}"><strong>Status:</strong> {health_status.upper()}</p>
                    <p>{summary}</p>
                </div>

                <div class="section">
                    <h3>Detailed Recommendations</h3>
                    <div class="recommendations">
                        {'<br>'.join(detailed_recs) if detailed_recs else 'No specific recommendations at this time.'}
                    </div>
                </div>

                <div class="links">
                    <h3>📚 Reference Links</h3>
                    <p>For more information on implementing these recommendations:</p>
                    <a href="https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-auto-scaling.html" target="_blank">ECS Auto Scaling Guide</a>
                    <a href="https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/performance.html" target="_blank">ECS Performance Best Practices</a>
                    <a href="https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-cpu-memory-error.html" target="_blank">CPU & Memory Optimization</a>
                    <a href="https://aws.amazon.com/blogs/containers/" target="_blank">AWS Containers Blog</a>
                </div>

                <div style="text-align: center; margin-top: 30px; color: #666;">
                    <p>Generated by ECS AI Monitoring System</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Get email source from environment variable
        email_source = Config.EMAIL_SOURCE
        email_cc = Config.EMAIL_CC or ""

        # Parse comma-separated CC addresses
        cc_addresses = (
            [addr.strip() for addr in email_cc.split(",") if addr.strip()]
            if email_cc
            else []
        )

        # Build destination
        destination = {"ToAddresses": [email]}
        if cc_addresses:
            destination["CcAddresses"] = cc_addresses

        # Send email
        response = ses_client.send_email(
            Source=email_source,
            Destination=destination,
            Message={
                "Subject": {
                    "Data": f'ECS Recommendations - {account_info["account_name"]} ({health_status.upper()})'
                },
                "Body": {
                    "Html": {"Data": html_body},
                    "Text": {
                        "Data": f"ECS Recommendations for {account_info['account_name']}\n\nHealth: {health_status}\n\nSummary: {summary}\n\nRecommendations:\n"
                        + "\n".join(detailed_recs)
                    },
                },
            },
        )

        logger.info(f"Email sent successfully. MessageId: {response['MessageId']}")

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise e


@app.get("/recommendations/{account_id}/{cluster_name}/{service_name}")
async def get_service_recommendations(
    account_id: str, cluster_name: str, service_name: str
):
    monitor = await get_monitor(account_id)
    ai_recommender = ai_recommenders.get(account_id)

    try:
        service_metrics = await monitor.get_service_specific_metrics(
            cluster_name, service_name
        )
        service_logs = await monitor.get_service_logs(cluster_name, service_name)

        from ai_recommender_service import generate_service_recommendations

        bedrock_client = ai_recommender.bedrock if ai_recommender else None
        model_id = ai_recommender.model_id if ai_recommender else None

        recommendations = await generate_service_recommendations(
            bedrock_client,
            model_id,
            service_metrics,
            service_logs,
            cluster_name,
            service_name,
        )

        # Add recommendations to chat history
        if account_id not in chat_history:
            chat_history[account_id] = []

        # Clear previous chat and add new context
        chat_history[account_id] = []

        # Add system context
        context_msg = f"You are an AWS ECS expert assistant. We are discussing ECS service '{service_name}' in cluster '{cluster_name}' for account {account_id}."
        chat_history[account_id].append(
            {"role": "system", "content": [{"text": context_msg}]}
        )

        # Build comprehensive metrics context
        metrics_context = []

        # CPU Metrics
        if service_metrics.get("cpu"):
            cpu_data = service_metrics["cpu"]
            if cpu_data:
                cpu_avg = sum(dp["Average"] for dp in cpu_data) / len(cpu_data)
                cpu_max = max(dp["Maximum"] for dp in cpu_data)
                metrics_context.append(
                    f"CPU: Average {cpu_avg:.1f}%, Maximum {cpu_max:.1f}%"
                )

        # Memory Metrics
        if service_metrics.get("memory"):
            memory_data = service_metrics["memory"]
            if memory_data:
                memory_avg = sum(dp["Average"] for dp in memory_data) / len(memory_data)
                memory_max = max(dp["Maximum"] for dp in memory_data)
                metrics_context.append(
                    f"Memory: Average {memory_avg:.1f}%, Maximum {memory_max:.1f}%"
                )

        # Target Group Metrics
        if service_metrics.get("target_group"):
            for tg_name, tg_data in service_metrics["target_group"].items():
                tg_details = []
                if tg_data.get("healthy_hosts"):
                    healthy_avg = sum(
                        dp["Average"] for dp in tg_data["healthy_hosts"]
                    ) / len(tg_data["healthy_hosts"])
                    tg_details.append(f"Healthy Hosts: {healthy_avg:.1f}")
                if tg_data.get("unhealthy_hosts"):
                    unhealthy_avg = sum(
                        dp["Average"] for dp in tg_data["unhealthy_hosts"]
                    ) / len(tg_data["unhealthy_hosts"])
                    tg_details.append(f"Unhealthy Hosts: {unhealthy_avg:.1f}")
                if tg_data.get("response_time"):
                    response_avg = sum(
                        dp["Average"] for dp in tg_data["response_time"]
                    ) / len(tg_data["response_time"])
                    tg_details.append(f"Response Time: {response_avg:.3f}s")
                if tg_data.get("request_count"):
                    request_avg = sum(
                        dp["Sum"] for dp in tg_data["request_count"]
                    ) / len(tg_data["request_count"])
                    tg_details.append(f"Requests: {request_avg:.0f}/period")

                if tg_details:
                    metrics_context.append(
                        f"Target Group {tg_name}: {', '.join(tg_details)}"
                    )

        # Add comprehensive metrics and recommendations as assistant message
        metrics_summary = (
            "; ".join(metrics_context)
            if metrics_context
            else "No detailed metrics available"
        )
        rec_msg = f"I have analyzed service '{service_name}' in cluster '{cluster_name}'. Current Metrics: {metrics_summary}. Recommendations: {json.dumps(recommendations, indent=2)}"
        chat_history[account_id].append(
            {"role": "assistant", "content": [{"text": rec_msg}]}
        )

        return recommendations
    except Exception as e:
        logger.error(f"Error getting service recommendations: {e}")
        return {"error": str(e), "service": service_name, "cluster": cluster_name}


@app.post("/accounts/{account_id}/refresh")
async def refresh_account_data(account_id: str):
    """Refresh cluster and service data for an account"""
    try:
        monitor = await get_monitor(account_id)

        # Force refresh cluster data
        await monitor.monitor_clusters()
        cluster_details = await monitor.get_cluster_details()

        # Store updated data
        await knowledge_db.store_cluster_data(account_id, cluster_details)

        return {
            "status": "success",
            "message": "Account data refreshed successfully",
            "cluster_details": cluster_details,
            "refreshed_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error refreshing account data: {e}")
        return {"error": str(e), "account_id": account_id}


@app.get("/service-details/{account_id}/{cluster_name}/{service_name}")
async def get_service_details(account_id: str, cluster_name: str, service_name: str):
    """Get detailed information for a specific service"""
    try:
        cluster_details = await knowledge_db.get_cluster_data(account_id)

        if not cluster_details or cluster_name not in cluster_details:
            raise HTTPException(404, "Cluster not found")

        service_info = None
        for service in cluster_details[cluster_name]:
            if service["name"] == service_name:
                service_info = service
                break

        if not service_info:
            raise HTTPException(404, "Service not found")

        return {
            "service_name": service_info["name"],
            "cluster_name": cluster_name,
            "status": service_info["status"],
            "running_count": service_info["running_count"],
            "desired_count": service_info["desired_count"],
            "cpu_avg": service_info.get("cpu_avg", 0),
            "cpu_max": service_info.get("cpu_max", 0),
            "memory_avg": service_info.get("memory_avg", 0),
            "memory_max": service_info.get("memory_max", 0),
            "target_groups": service_info.get("target_groups", {}),
            "last_updated": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting service details: {e}")
        raise HTTPException(500, f"Error retrieving service details: {str(e)}")


class ChatMessage(BaseModel):
    message: str
    context: Optional[Dict] = None
    reset_chat: Optional[bool] = False


@app.get("/cluster-recommendations/{account_id}/{cluster_name}")
async def get_specific_cluster_recommendations(account_id: str, cluster_name: str):
    """Generate recommendations for a specific cluster only"""
    try:
        monitor = await get_monitor(account_id)
        ai_recommender = ai_recommenders.get(account_id)

        # Get cluster data from knowledge base
        cluster_data = await knowledge_db.get_cluster_data(account_id)

        if not cluster_data:
            # If no cached data, get fresh data
            await monitor.monitor_clusters()
            cluster_data = await monitor.get_cluster_details()
            await knowledge_db.store_cluster_data(account_id, cluster_data)

        # Check if the specific cluster exists
        if cluster_name not in cluster_data:
            available_clusters = list(cluster_data.keys())
            raise HTTPException(
                404,
                f"Cluster '{cluster_name}' not found. Available clusters: {', '.join(available_clusters)}",
            )

        services = cluster_data[cluster_name]

        # Process services in parallel
        async def process_service(service):
            service_name = service["name"]
            try:
                # Get service-specific metrics
                service_metrics = await monitor.get_service_specific_metrics(
                    cluster_name, service_name
                )
                service_logs = await monitor.get_service_logs(
                    cluster_name, service_name
                )

                # Generate service recommendations
                from ai_recommender_service import generate_service_recommendations

                bedrock_client = ai_recommender.bedrock if ai_recommender else None
                model_id = ai_recommender.model_id if ai_recommender else None

                recommendation = await generate_service_recommendations(
                    bedrock_client,
                    model_id,
                    service_metrics,
                    service_logs,
                    cluster_name,
                    service_name,
                )

                # Store recommendation in the new table
                await knowledge_db.store_service_recommendation(
                    account_id, cluster_name, service_name, recommendation
                )

                # Add service details with recommendation
                return {
                    "service_name": service_name,
                    "cluster_name": cluster_name,
                    "service_details": service,
                    "service_health": recommendation.get("service_health", "unknown"),
                    "scaling_action": recommendation.get("scaling_action", "no_change"),
                    "priority": recommendation.get("priority", "medium"),
                    "reason": recommendation.get("reason", ""),
                    "recommendations": recommendation.get("recommendations", []),
                    "full_recommendation": recommendation,
                }

            except Exception as e:
                logger.error(
                    f"Error processing service {service_name} in cluster {cluster_name}: {e}"
                )
                # Return service with error status
                return {
                    "service_name": service_name,
                    "cluster_name": cluster_name,
                    "service_details": service,
                    "service_health": "error",
                    "scaling_action": "no_change",
                    "priority": "low",
                    "reason": f"Error generating recommendations: {str(e)}",
                    "recommendations": [],
                    "full_recommendation": {"error": str(e)},
                }

        # Process all services in parallel
        cluster_results = await asyncio.gather(
            *[process_service(service) for service in services]
        )

        # Sort services by priority (high -> medium -> low) then by health (error -> critical -> warning -> good)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        health_order = {
            "error": 0,
            "critical": 1,
            "warning": 2,
            "good": 3,
            "unknown": 4,
        }

        cluster_results.sort(
            key=lambda x: (
                priority_order.get(x.get("priority", "medium"), 1),
                health_order.get(x.get("service_health", "unknown"), 4),
            )
        )

        # Calculate health summary for this cluster only
        health_counts = {
            "good": 0,
            "warning": 0,
            "critical": 0,
            "error": 0,
            "unknown": 0,
        }
        scaling_counts = {"scale_up": 0, "scale_down": 0, "no_change": 0}
        priority_counts = {"high": 0, "medium": 0, "low": 0}

        for service in cluster_results:
            health = service.get("service_health", "unknown")
            scaling = service.get("scaling_action", "no_change")
            priority = service.get("priority", "medium")

            health_counts[health] = health_counts.get(health, 0) + 1
            scaling_counts[scaling] = scaling_counts.get(scaling, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return {
            "account_id": account_id,
            "cluster_name": cluster_name,
            "timestamp": datetime.now().isoformat(),
            "services": cluster_results,
            "summary": {
                "total_services": len(cluster_results),
                "health_distribution": health_counts,
                "scaling_distribution": scaling_counts,
                "priority_distribution": priority_counts,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting cluster recommendations for {cluster_name}: {e}")
        raise HTTPException(500, f"Error processing cluster recommendations: {str(e)}")


@app.get("/cluster-recommendations/{account_id}")
async def get_cluster_recommendations(account_id: str):
    """Get cluster data and generate service recommendations for each service"""
    try:
        monitor = await get_monitor(account_id)
        ai_recommender = ai_recommenders.get(account_id)

        # Get cluster data from knowledge base
        cluster_data = await knowledge_db.get_cluster_data_with_recommendations(
            account_id
        )

        if not cluster_data:
            # If no cached data, get fresh data
            await monitor.monitor_clusters()
            cluster_data = await monitor.get_cluster_details()
            await knowledge_db.store_cluster_data(account_id, cluster_data)

        results = {}

        # Process services in parallel for each cluster
        async def process_service(cluster_name, service):
            service_name = service["name"]
            try:
                # Get service-specific metrics
                service_metrics = await monitor.get_service_specific_metrics(
                    cluster_name, service_name
                )
                service_logs = await monitor.get_service_logs(
                    cluster_name, service_name
                )

                # Generate service recommendations
                from ai_recommender_service import generate_service_recommendations

                bedrock_client = ai_recommender.bedrock if ai_recommender else None
                model_id = ai_recommender.model_id if ai_recommender else None

                recommendation = await generate_service_recommendations(
                    bedrock_client,
                    model_id,
                    service_metrics,
                    service_logs,
                    cluster_name,
                    service_name,
                )

                # Store recommendation in the new table
                await knowledge_db.store_service_recommendation(
                    account_id, cluster_name, service_name, recommendation
                )

                # Add service details with recommendation
                return {
                    "service_name": service_name,
                    "cluster_name": cluster_name,
                    "service_details": service,
                    "service_health": recommendation.get("service_health", "unknown"),
                    "scaling_action": recommendation.get("scaling_action", "no_change"),
                    "priority": recommendation.get("priority", "medium"),
                    "reason": recommendation.get("reason", ""),
                    "recommendations": recommendation.get("recommendations", []),
                    "full_recommendation": recommendation,
                }

            except Exception as e:
                logger.error(
                    f"Error processing service {service_name} in cluster {cluster_name}: {e}"
                )
                # Return service with error status
                return {
                    "service_name": service_name,
                    "cluster_name": cluster_name,
                    "service_details": service,
                    "service_health": "error",
                    "scaling_action": "no_change",
                    "priority": "low",
                    "reason": f"Error generating recommendations: {str(e)}",
                    "recommendations": [],
                    "full_recommendation": {"error": str(e)},
                }

        # Process all clusters and services in parallel
        for cluster_name, services in cluster_data.items():
            cluster_results = await asyncio.gather(
                *[process_service(cluster_name, service) for service in services]
            )
            results[cluster_name] = cluster_results

        return {
            "account_id": account_id,
            "timestamp": datetime.now().isoformat(),
            "clusters": results,
            "summary": {
                "total_clusters": len(results),
                "total_services": sum(len(services) for services in results.values()),
                "health_summary": _get_health_summary(results),
            },
        }

    except Exception as e:
        logger.error(f"Error getting cluster recommendations: {e}")
        raise HTTPException(500, f"Error processing cluster recommendations: {str(e)}")


def _get_health_summary(results: Dict) -> Dict:
    """Generate health summary from cluster results"""
    health_counts = {"good": 0, "warning": 0, "critical": 0, "error": 0, "unknown": 0}
    scaling_counts = {"scale_up": 0, "scale_down": 0, "no_change": 0}
    priority_counts = {"high": 0, "medium": 0, "low": 0}

    for cluster_services in results.values():
        for service in cluster_services:
            health = service.get("service_health", "unknown")
            scaling = service.get("scaling_action", "no_change")
            priority = service.get("priority", "medium")

            health_counts[health] = health_counts.get(health, 0) + 1
            scaling_counts[scaling] = scaling_counts.get(scaling, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

    return {
        "health_distribution": health_counts,
        "scaling_distribution": scaling_counts,
        "priority_distribution": priority_counts,
    }


@app.get("/service-recommendations/{account_id}")
async def get_service_recommendations_by_filter(
    account_id: str, health_status: str = None, priority: str = None
):
    """Get service recommendations filtered by health status and/or priority"""
    try:
        recommendations = await knowledge_db.get_service_recommendations_by_health(
            account_id, health_status, priority
        )

        filters = []
        if health_status:
            filters.append(f"health={health_status}")
        if priority:
            filters.append(f"priority={priority}")

        return {
            "account_id": account_id,
            "filter": ", ".join(filters) if filters else "all",
            "count": len(recommendations),
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting filtered service recommendations: {e}")
        raise HTTPException(500, f"Error retrieving recommendations: {str(e)}")


@app.post("/trigger-daily-recommendations")
async def trigger_daily_recommendations():
    """Manually trigger daily cluster recommendations generation (for testing)"""
    try:
        await generate_daily_cluster_recommendations()
        return {
            "status": "success",
            "message": "Daily cluster recommendations generated successfully",
        }
    except Exception as e:
        logger.error(f"Error triggering daily recommendations: {e}")
        raise HTTPException(500, f"Error generating daily recommendations: {str(e)}")


@app.post("/trigger-daily-report")
async def trigger_daily_report():
    """Manually trigger daily high-priority reports (for testing)"""
    try:
        await send_daily_high_priority_reports()
        return {
            "status": "success",
            "message": "Daily high-priority reports sent successfully",
        }
    except Exception as e:
        logger.error(f"Error triggering daily report: {e}")
        raise HTTPException(500, f"Error sending daily reports: {str(e)}")


@app.post("/chat/{account_id}")
async def chat_with_ai(account_id: str, chat_message: ChatMessage):
    """Chat with AI about ECS recommendations and scenarios"""
    if account_id not in ai_recommenders:
        raise HTTPException(404, "Account not found")

    ai_recommender = ai_recommenders[account_id]

    try:
        # Reset chat if requested
        if chat_message.reset_chat:
            chat_history[account_id] = []

        # Update chat history with frontend context if provided
        context = chat_message.context or {}
        if (
            context
            and account_id in chat_history
            and len(chat_history[account_id]) >= 2
        ):
            # Update existing system message with detailed context
            details = []
            if context.get("service_name") and context.get("cluster_name"):
                details.append(
                    f"We are discussing ECS service '{context['service_name']}' in cluster '{context['cluster_name']}'"
                )
            if context.get("service_health"):
                details.append(f"Service health status: {context['service_health']}")
            if context.get("scaling_action"):
                details.append(
                    f"Recommended scaling action: {context['scaling_action']}"
                )
            if context.get("priority"):
                details.append(f"Priority level: {context['priority']}")
            if context.get("reason"):
                details.append(f"Initial analysis: {context['reason']}")
            if context.get("recommendations") and isinstance(
                context["recommendations"], list
            ):
                details.append(
                    f"Initial recommendations: {'; '.join(context['recommendations'][:3])}"
                )

            # Add service metrics context if available
            if context.get("service_name") and context.get("cluster_name"):
                try:
                    monitor = await get_monitor(account_id)
                    service_metrics = await monitor.get_service_specific_metrics(
                        context["cluster_name"], context["service_name"]
                    )

                    # Build metrics context
                    metrics_context = []
                    if service_metrics.get("cpu"):
                        cpu_data = service_metrics["cpu"]
                        if cpu_data:
                            cpu_avg = sum(dp["Average"] for dp in cpu_data) / len(
                                cpu_data
                            )
                            cpu_max = max(dp["Maximum"] for dp in cpu_data)
                            metrics_context.append(
                                f"CPU: Average {cpu_avg:.1f}%, Maximum {cpu_max:.1f}%"
                            )

                    if service_metrics.get("memory"):
                        memory_data = service_metrics["memory"]
                        if memory_data:
                            memory_avg = sum(dp["Average"] for dp in memory_data) / len(
                                memory_data
                            )
                            memory_max = max(dp["Maximum"] for dp in memory_data)
                            metrics_context.append(
                                f"Memory: Average {memory_avg:.1f}%, Maximum {memory_max:.1f}%"
                            )

                    if service_metrics.get("target_group"):
                        for tg_name, tg_data in service_metrics["target_group"].items():
                            tg_details = []
                            if tg_data.get("healthy_hosts"):
                                healthy_avg = sum(
                                    dp["Average"] for dp in tg_data["healthy_hosts"]
                                ) / len(tg_data["healthy_hosts"])
                                tg_details.append(f"Healthy Hosts: {healthy_avg:.1f}")
                            if tg_data.get("response_time"):
                                response_avg = sum(
                                    dp["Average"] for dp in tg_data["response_time"]
                                ) / len(tg_data["response_time"])
                                tg_details.append(f"Response Time: {response_avg:.3f}s")
                            if tg_data.get("request_count"):
                                request_avg = sum(
                                    dp["Sum"] for dp in tg_data["request_count"]
                                ) / len(tg_data["request_count"])
                                tg_details.append(f"Requests: {request_avg:.0f}/period")

                            if tg_details:
                                metrics_context.append(
                                    f"Target Group {tg_name}: {', '.join(tg_details)}"
                                )

                    if metrics_context:
                        details.append(f"Current Metrics: {'; '.join(metrics_context)}")
                except Exception as e:
                    logger.error(f"Error getting service metrics for chat context: {e}")

            if details:
                enhanced_context = ". ".join(details)
                enhanced_system_msg = f"You are an AWS ECS expert assistant. IMPORTANT CONTEXT: {enhanced_context}. When users ask about 'which service' or 'what recommendations', refer to this context. Always remember this is the service/recommendations we are discussing."
                chat_history[account_id][0] = {
                    "role": "system",
                    "content": [{"text": enhanced_system_msg}],
                }

        # Initialize chat history if not exists (fallback)
        if account_id not in chat_history:
            chat_history[account_id] = []
            system_msg = "You are an AWS ECS expert assistant. Help users with ECS recommendations and scenarios."
            chat_history[account_id].append(
                {"role": "system", "content": [{"text": system_msg}]}
            )

        # Add user message to history
        chat_history[account_id].append(
            {"role": "user", "content": [{"text": chat_message.message}]}
        )

        if ai_recommender.bedrock:
            # Extract system message and user/assistant messages
            system_prompt = None
            conversation_messages = []

            for msg in chat_history[account_id]:
                if msg["role"] == "system":
                    system_prompt = msg["content"][0]["text"]
                else:
                    conversation_messages.append(msg)

            # Call Bedrock with system prompt separate from messages
            converse_params = {
                "modelId": ai_recommender.model_id,
                "messages": conversation_messages,
                "inferenceConfig": {
                    "maxTokens": Config.AI_CHAT_MAX_TOKENS,
                    "temperature": Config.AI_CHAT_TEMPERATURE,
                },
            }

            if system_prompt:
                converse_params["system"] = [{"text": system_prompt}]

            response = ai_recommender.bedrock.converse(**converse_params)

            ai_response = response["output"]["message"]["content"][0]["text"]

            # Add AI response to history
            chat_history[account_id].append(
                {"role": "assistant", "content": [{"text": ai_response}]}
            )

            # Keep only last N messages to avoid token limits
            if (
                len(chat_history[account_id]) > Config.CHAT_HISTORY_LIMIT + 1
            ):  # 1 system + N conversation messages
                chat_history[account_id] = (
                    chat_history[account_id][:1]
                    + chat_history[account_id][-Config.CHAT_HISTORY_LIMIT :]
                )
        else:
            ai_response = "AI chat is currently unavailable. Please check your Bedrock configuration."

        return {"response": ai_response, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return {
            "response": f"I'm having trouble processing your request right now. Error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


@app.post("/trigger-weekly-recommendations")
async def trigger_weekly_recommendations():
    """Manually trigger weekly cluster recommendations generation (for testing)"""
    try:
        await generate_weekly_cluster_recommendations()
        return {
            "status": "success",
            "message": "Weekly cluster recommendations generated successfully",
        }
    except Exception as e:
        logger.error(f"Error triggering weekly recommendations: {e}")
        raise HTTPException(500, f"Error generating weekly recommendations: {str(e)}")


@app.post("/trigger-weekly-report")
async def trigger_weekly_report():
    """Manually trigger weekly comprehensive reports (for testing)"""
    try:
        await send_weekly_comprehensive_reports()
        return {
            "status": "success",
            "message": "Weekly comprehensive reports sent successfully",
        }
    except Exception as e:
        logger.error(f"Error triggering weekly report: {e}")
        raise HTTPException(500, f"Error sending weekly reports: {str(e)}")


async def generate_daily_cluster_recommendations():
    """Generate cluster recommendations for all accounts daily at 7 AM"""
    logger.info("Starting daily cluster recommendations generation...")

    try:
        accounts = await knowledge_db.get_all_accounts()

        for account in accounts:
            account_id = account["account_id"]
            account_name = account["account_name"]

            try:
                if account_id in ai_recommenders:
                    monitor = await get_monitor(account_id)
                    ai_recommender = ai_recommenders.get(account_id)

                    # Get cluster data
                    await monitor.monitor_clusters()
                    cluster_data = await monitor.get_cluster_details()
                    await knowledge_db.store_cluster_data(account_id, cluster_data)

                    # Process services in parallel
                    async def process_service(cluster_name, service):
                        service_name = service["name"]
                        try:
                            service_metrics = (
                                await monitor.get_service_specific_metrics(
                                    cluster_name, service_name
                                )
                            )
                            service_logs = await monitor.get_service_logs(
                                cluster_name, service_name
                            )

                            from ai_recommender_service import (
                                generate_service_recommendations,
                            )

                            bedrock_client = (
                                ai_recommender.bedrock if ai_recommender else None
                            )
                            model_id = (
                                ai_recommender.model_id if ai_recommender else None
                            )

                            recommendation = await generate_service_recommendations(
                                bedrock_client,
                                model_id,
                                service_metrics,
                                service_logs,
                                cluster_name,
                                service_name,
                            )

                            await knowledge_db.store_service_recommendation(
                                account_id,
                                cluster_name,
                                service_name,
                                recommendation,
                            )
                            return True
                        except Exception as e:
                            logger.error(
                                f"Error processing service {cluster_name}/{service_name}: {e}"
                            )
                            return False

                    # Generate recommendations for all services in parallel
                    total_services = 0
                    for cluster_name, services in cluster_data.items():
                        total_services += len(services)
                        await asyncio.gather(
                            *[
                                process_service(cluster_name, service)
                                for service in services
                            ]
                        )

                    logger.info(
                        f"Generated recommendations for {account_name}: {total_services} services"
                    )
                else:
                    logger.info(f"Account {account_name} not active, skipping")

            except Exception as e:
                logger.error(
                    f"Error generating recommendations for {account_name}: {e}"
                )

    except Exception as e:
        logger.error(f"Error in daily cluster recommendations: {e}")


async def send_daily_high_priority_reports():
    """Send daily email reports for high-priority service recommendations"""
    logger.info("Starting daily high-priority reports...")

    try:
        accounts = await knowledge_db.get_all_accounts()

        for account in accounts:
            account_id = account["account_id"]
            account_name = account["account_name"]

            try:
                # Get high-priority recommendations
                high_priority_recs = (
                    await knowledge_db.get_service_recommendations_by_health(
                        account_id, priority="high"
                    )
                )

                if high_priority_recs:
                    await send_high_priority_email_report(account, high_priority_recs)
                    logger.info(
                        f"Sent high-priority report for {account_name} ({len(high_priority_recs)} services)"
                    )
                else:
                    logger.info(f"No high-priority recommendations for {account_name}")

            except Exception as e:
                logger.error(f"Error sending daily report for {account_name}: {e}")

    except Exception as e:
        logger.error(f"Error in daily high-priority reports: {e}")


async def generate_weekly_cluster_recommendations():
    """Generate cluster recommendations for all accounts weekly on Monday at 8 AM"""
    logger.info("Starting weekly cluster recommendations generation...")

    try:
        accounts = await knowledge_db.get_all_accounts()

        for account in accounts:
            account_id = account["account_id"]
            account_name = account["account_name"]

            try:
                if account_id in ai_recommenders:
                    monitor = await get_monitor(account_id)
                    ai_recommender = ai_recommenders.get(account_id)

                    # Get cluster data
                    await monitor.monitor_clusters()
                    cluster_data = await monitor.get_cluster_details()
                    await knowledge_db.store_cluster_data(account_id, cluster_data)

                    # Process services in parallel
                    async def process_service(cluster_name, service):
                        service_name = service["name"]
                        try:
                            service_metrics = (
                                await monitor.get_service_specific_metrics(
                                    cluster_name, service_name
                                )
                            )
                            service_logs = await monitor.get_service_logs(
                                cluster_name, service_name
                            )

                            from ai_recommender_service import (
                                generate_service_recommendations,
                            )

                            bedrock_client = (
                                ai_recommender.bedrock if ai_recommender else None
                            )
                            model_id = (
                                ai_recommender.model_id if ai_recommender else None
                            )

                            recommendation = await generate_service_recommendations(
                                bedrock_client,
                                model_id,
                                service_metrics,
                                service_logs,
                                cluster_name,
                                service_name,
                            )

                            await knowledge_db.store_service_recommendation(
                                account_id,
                                cluster_name,
                                service_name,
                                recommendation,
                            )
                            return True
                        except Exception as e:
                            logger.error(
                                f"Error processing service {cluster_name}/{service_name}: {e}"
                            )
                            return False

                    # Generate recommendations for all services in parallel
                    total_services = 0
                    for cluster_name, services in cluster_data.items():
                        total_services += len(services)
                        await asyncio.gather(
                            *[
                                process_service(cluster_name, service)
                                for service in services
                            ]
                        )

                    logger.info(
                        f"Generated weekly recommendations for {account_name}: {total_services} services"
                    )
                else:
                    logger.info(f"Account {account_name} not active, skipping")

            except Exception as e:
                logger.error(
                    f"Error generating weekly recommendations for {account_name}: {e}"
                )

    except Exception as e:
        logger.error(f"Error in weekly cluster recommendations: {e}")


async def send_weekly_comprehensive_reports():
    """Send weekly comprehensive email reports for all service recommendations"""
    logger.info("Starting weekly comprehensive reports...")

    try:
        accounts = await knowledge_db.get_all_accounts()

        for account in accounts:
            account_id = account["account_id"]
            account_name = account["account_name"]

            try:
                # Get all recommendations
                all_recs = await knowledge_db.get_service_recommendations_by_health(
                    account_id
                )

                if all_recs:
                    await send_comprehensive_email_report(account, all_recs)
                    logger.info(
                        f"Sent weekly comprehensive report for {account_name} ({len(all_recs)} services)"
                    )
                else:
                    logger.info(
                        f"No recommendations for weekly report for {account_name}"
                    )

            except Exception as e:
                logger.error(f"Error sending weekly report for {account_name}: {e}")

    except Exception as e:
        logger.error(f"Error in weekly comprehensive reports: {e}")


async def send_high_priority_email_report(
    account_info: Dict, recommendations: List[Dict]
):
    """Send HTML email report for high-priority recommendations"""
    try:
        ses_client = boto3.client("ses", region_name=account_info["region"])

        # Build HTML content
        service_details = []
        critical_count = 0
        warning_count = 0
        scale_up_count = 0

        for rec in recommendations:
            health = rec["service_health"]
            scaling = rec["scaling_action"]

            if health == "critical":
                critical_count += 1
            elif health == "warning":
                warning_count += 1

            if scaling == "scale_up":
                scale_up_count += 1

            health_color = {
                "critical": "#dc3545",
                "warning": "#ffc107",
                "good": "#28a745",
            }.get(health, "#6c757d")
            scaling_color = {
                "scale_up": "#dc3545",
                "scale_down": "#28a745",
                "no_change": "#6c757d",
            }.get(scaling, "#6c757d")

            service_details.append(
                f"""
            <div style="margin: 10px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid {health_color}; border-radius: 5px;">
                <h4 style="margin: 0 0 8px 0; color: #333;">{rec['cluster']}/{rec['service']}</h4>
                <div style="margin: 5px 0;">
                    <span style="background: {health_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">{health.upper()}</span>
                    <span style="background: {scaling_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; margin-left: 5px;">{scaling.replace('_', ' ').upper()}</span>
                </div>
                <div style="margin: 8px 0; color: #666;">
                    <strong>Recommendations:</strong>
                    <ul style="margin: 5px 0; padding-left: 20px;">
            """
            )

            full_rec = rec["full_recommendation"]
            if isinstance(full_rec.get("recommendations"), list):
                for recommendation in full_rec["recommendations"]:
                    service_details.append(f"<li>{recommendation}</li>")

            service_details.append("</ul></div></div>")

        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: linear-gradient(135deg, #dc3545 0%, #ffc107 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .summary {{ background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 Daily High-Priority ECS Recommendations</h1>
                <p>Critical Services Requiring Immediate Attention</p>
            </div>

            <div class="content">
                <div class="summary">
                    <h3>📊 Summary for {account_info['account_name']}</h3>
                    <p><strong>Account ID:</strong> {account_info['account_id']}</p>
                    <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p><strong>High-Priority Services:</strong> {len(recommendations)}</p>
                    <p><strong>Critical Services:</strong> {critical_count} | <strong>Warning Services:</strong> {warning_count}</p>
                    <p><strong>Services Needing Scale-Up:</strong> {scale_up_count}</p>
                </div>

                <h3>🔥 High-Priority Service Recommendations</h3>
                {''.join(service_details)}

                <div class="footer">
                    <p>This is an automated daily report for high-priority ECS service recommendations.</p>
                    <p>Generated by ECS AI Monitoring System</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Get email configuration from environment variables
        email_source = Config.EMAIL_SOURCE
        email_destination = Config.EMAIL_DESTINATION
        email_cc = Config.EMAIL_CC or ""

        # Parse comma-separated email addresses
        to_addresses = [
            email.strip() for email in email_destination.split(",") if email.strip()
        ]
        cc_addresses = (
            [email.strip() for email in email_cc.split(",") if email.strip()]
            if email_cc
            else []
        )

        # Build destination
        destination = {"ToAddresses": to_addresses}
        if cc_addresses:
            destination["CcAddresses"] = cc_addresses

        # Send email
        response = ses_client.send_email(
            Source=email_source,
            Destination=destination,
            Message={
                "Subject": {
                    "Data": f'🚨 Daily High-Priority ECS Report - {account_info["account_name"]} ({len(recommendations)} services)'
                },
                "Body": {"Html": {"Data": html_body}},
            },
        )

        logger.info(
            f"High-priority email sent successfully. MessageId: {response['MessageId']}"
        )

    except Exception as e:
        logger.error(f"Failed to send high-priority email: {e}")
        raise e


async def send_comprehensive_email_report(
    account_info: Dict, recommendations: List[Dict]
):
    """Send HTML email report for comprehensive weekly recommendations"""
    try:
        ses_client = boto3.client("ses", region_name=account_info["region"])

        # Group recommendations by priority and health
        priority_groups = {"high": [], "medium": [], "low": []}
        health_counts = {"critical": 0, "warning": 0, "good": 0, "error": 0}
        scaling_counts = {"scale_up": 0, "scale_down": 0, "no_change": 0}

        for rec in recommendations:
            priority = rec.get("priority", "medium")
            health = rec.get("service_health", "unknown")
            scaling = rec.get("scaling_action", "no_change")

            if priority in priority_groups:
                priority_groups[priority].append(rec)

            if health in health_counts:
                health_counts[health] += 1

            if scaling in scaling_counts:
                scaling_counts[scaling] += 1

        # Build HTML sections for each priority
        priority_sections = []
        for priority in ["high", "medium", "low"]:
            if priority_groups[priority]:
                priority_color = {
                    "high": "#dc3545",
                    "medium": "#ffc107",
                    "low": "#28a745",
                }.get(priority, "#6c757d")
                priority_sections.append(
                    f'<h3 style="color: {priority_color}; text-transform: uppercase;">{priority} Priority ({len(priority_groups[priority])} services)</h3>'
                )

                for rec in priority_groups[priority]:
                    health = rec["service_health"]
                    scaling = rec["scaling_action"]

                    health_color = {
                        "critical": "#dc3545",
                        "warning": "#ffc107",
                        "good": "#28a745",
                    }.get(health, "#6c757d")
                    scaling_color = {
                        "scale_up": "#dc3545",
                        "scale_down": "#28a745",
                        "no_change": "#6c757d",
                    }.get(scaling, "#6c757d")

                    priority_sections.append(
                        f"""
                    <div style="margin: 10px 0; padding: 15px; background: #f8f9fa; border-left: 4px solid {health_color}; border-radius: 5px;">
                        <h4 style="margin: 0 0 8px 0; color: #333;">{rec['cluster']}/{rec['service']}</h4>
                        <div style="margin: 5px 0;">
                            <span style="background: {health_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold;">{health.upper()}</span>
                            <span style="background: {scaling_color}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; margin-left: 5px;">{scaling.replace('_', ' ').upper()}</span>
                        </div>
                        <div style="margin: 8px 0; color: #666;">
                            <strong>Recommendations:</strong>
                            <ul style="margin: 5px 0; padding-left: 20px;">
                    """
                    )

                    full_rec = rec["full_recommendation"]
                    if isinstance(full_rec.get("recommendations"), list):
                        for recommendation in full_rec["recommendations"]:
                            priority_sections.append(f"<li>{recommendation}</li>")

                    priority_sections.append("</ul></div></div>")

        html_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; }}
                .summary {{ background: #e3f2fd; border: 1px solid #90caf9; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Weekly Comprehensive ECS Report</h1>
                <p>Complete Infrastructure Analysis & Recommendations</p>
            </div>

            <div class="content">
                <div class="summary">
                    <h3>📈 Weekly Summary for {account_info['account_name']}</h3>
                    <p><strong>Account ID:</strong> {account_info['account_id']}</p>
                    <p><strong>Report Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                    <p><strong>Total Services Analyzed:</strong> {len(recommendations)}</p>
                    <p><strong>Health Distribution:</strong> Critical: {health_counts['critical']} | Warning: {health_counts['warning']} | Good: {health_counts['good']} | Error: {health_counts['error']}</p>
                    <p><strong>Scaling Actions:</strong> Scale Up: {scaling_counts['scale_up']} | Scale Down: {scaling_counts['scale_down']} | No Change: {scaling_counts['no_change']}</p>
                    <p><strong>Priority Distribution:</strong> High: {len(priority_groups['high'])} | Medium: {len(priority_groups['medium'])} | Low: {len(priority_groups['low'])}</p>
                </div>

                <h3>🔍 Detailed Recommendations by Priority</h3>
                {''.join(priority_sections)}

                <div class="footer">
                    <p>This is an automated weekly comprehensive report for all ECS service recommendations.</p>
                    <p>Generated by ECS AI Monitoring System</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Get email configuration from environment variables
        email_source = Config.EMAIL_SOURCE
        email_destination = Config.EMAIL_DESTINATION
        email_cc = Config.EMAIL_CC or ""

        # Parse comma-separated email addresses
        to_addresses = [
            email.strip() for email in email_destination.split(",") if email.strip()
        ]
        cc_addresses = (
            [email.strip() for email in email_cc.split(",") if email.strip()]
            if email_cc
            else []
        )

        # Build destination
        destination = {"ToAddresses": to_addresses}
        if cc_addresses:
            destination["CcAddresses"] = cc_addresses

        # Send email
        response = ses_client.send_email(
            Source=email_source,
            Destination=destination,
            Message={
                "Subject": {
                    "Data": f'📊 Weekly ECS Comprehensive Report - {account_info["account_name"]} ({len(recommendations)} services)'
                },
                "Body": {"Html": {"Data": html_body}},
            },
        )

        logger.info(
            f"Weekly comprehensive email sent successfully. MessageId: {response['MessageId']}"
        )

    except Exception as e:
        logger.error(f"Failed to send weekly comprehensive email: {e}")
        raise e


async def start_monitoring(account_id: str):
    while True:
        try:
            monitor = await get_monitor(account_id)
            await monitor.monitor_clusters()
            await asyncio.sleep(Config.MONITORING_INTERVAL)
        except Exception as e:
            logger.error(f"Monitoring error for {account_id}: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=Config.APP_PORT)
