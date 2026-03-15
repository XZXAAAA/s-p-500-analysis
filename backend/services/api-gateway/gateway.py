"""
API Gateway (Gateway Service)
Port: 5000
Responsibilities: Request routing, authentication, rate limiting, logging
"""

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import logging
import os
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="API Gateway",
    description="S&P 500 Stock Sentiment Analysis - API Gateway",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service discovery
SERVICES = {
    "auth": os.getenv("AUTH_SERVICE_URL", "http://auth-service:5001"),
    "data": os.getenv("DATA_SERVICE_URL", "http://data-service:5002"),
    "viz": os.getenv("VIZ_SERVICE_URL", "http://viz-service:5003"),
}

logger.info(f"🔗 Service URLs: {SERVICES}")


@app.get("/")
async def root():
    """API Gateway root endpoint"""
    return {
        "service": "S&P 500 Stock Sentiment Analysis API Gateway",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health or /api/health",
            "auth": "/api/auth/*",
            "data": "/api/data/*",
            "sentiment": "/api/sentiment/*",
            "viz": "/api/viz/*",
            "documentation": {
                "auth_service": "http://localhost:5001/docs",
                "data_service": "http://localhost:5002/docs",
                "viz_service": "http://localhost:5003/docs"
            }
        },
        "frontend": "http://localhost:3000"
    }


@app.get("/health")
async def health():
    """Gateway health check"""
    return {"status": "healthy", "service": "api-gateway"}

@app.get("/api/health")
async def api_health():
    """Check health status of all services"""
    health_status = {}
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for service_name, service_url in SERVICES.items():
            try:
                response = await client.get(f"{service_url}/health")
                health_status[service_name] = {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "status_code": response.status_code
                }
            except Exception as e:
                logger.error(f"✗ {service_name} health check failed: {str(e)}")
                health_status[service_name] = {"status": "unreachable", "error": str(e)}
    
    return {"gateway": "healthy", "services": health_status}


@app.api_route("/api/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_auth(path: str, request: Request):
    """Proxy authentication service requests"""
    return await proxy_request("auth", path, request)


@app.api_route("/api/data/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_data(path: str, request: Request):
    """Proxy data service requests"""
    return await proxy_request("data", path, request)


@app.api_route("/api/viz/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_viz(path: str, request: Request):
    """Proxy visualization service requests"""
    return await proxy_request("viz", path, request)


def _normalize_path(service: str, path: str) -> str:
    """Add real backend path prefix based on service type"""
    normalized = path.lstrip("/")
    
    if service == "auth":
        # Backend endpoints start with /auth/ or /users/, add /auth/ for others
        if not normalized.startswith(("auth/", "users/")):
            normalized = f"auth/{normalized}"
    elif service == "data":
        # Refresh/status endpoints are under /data/, sentiment-related under /sentiment/
        if normalized in ("refresh", "status"):
            normalized = f"data/{normalized}"
        elif not normalized.startswith(("data/", "sentiment/")):
            normalized = f"sentiment/{normalized}"
    elif service == "viz":
        if not normalized.startswith("viz/"):
            normalized = f"viz/{normalized}"
    
    return normalized


async def proxy_request(service: str, path: str, request: Request):
    """Generic proxy function"""
    if service not in SERVICES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    
    service_url = SERVICES[service].rstrip("/")
    normalized_path = _normalize_path(service, path)
    full_url = f"{service_url}/{normalized_path}"
    
    # Build query parameters
    if request.query_params:
        full_url += f"?{request.query_params}"
    
    try:
        # Read request body
        body = await request.body()
        
        logger.info(f"📤 {request.method} {full_url}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=full_url,
                content=body,
                headers={
                    key: value for key, value in request.headers.items()
                    if key.lower() not in ["host", "connection"]
                },
                follow_redirects=True
            )
            
            logger.info(f"📥 {response.status_code} from {service}")
            
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    
    except httpx.TimeoutException:
        logger.error(f"✗ {service} request timeout")
        return JSONResponse(
            {"error": f"{service} service timeout"},
            status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )
    except httpx.ConnectError:
        logger.error(f"✗ Cannot connect to {service}")
        return JSONResponse(
            {"error": f"Cannot connect to {service} service"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        logger.error(f"✗ Proxy request failed: {str(e)}")
        return JSONResponse(
            {"error": str(e)},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

