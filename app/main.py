# =============================================================================
# SmartApply Web Agent - FastAPI Application Entry Point
# =============================================================================
# Main FastAPI application with endpoints for the web automation agent.
# Run with: uvicorn app.main:app --host 0.0.0.0 --port 8000
# =============================================================================

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import get_settings
from app.agent.web_agent import WebAgent, create_web_agent


# =============================================================================
# Request/Response Models
# =============================================================================

class AgentTaskRequest(BaseModel):
    """Request model for agent task execution."""
    task: str = Field(
        ...,
        description="The task description for the web agent",
        min_length=1,
        max_length=2000,
        examples=["Search for the latest Python news and summarize the top 3 articles"]
    )
    

class AgentTaskResponse(BaseModel):
    """Response model for agent task results."""
    success: bool
    task: str
    result: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    environment: str


# =============================================================================
# Application Lifespan (Startup/Shutdown)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown events.
    
    Startup:
        - Validate configuration
        - Log startup message
    
    Shutdown:
        - Clean up resources
    """
    # Startup
    settings = get_settings()
    
    # Validate that API key is configured
    if not settings.google_api_key:
        print("⚠️  WARNING: GOOGLE_API_KEY not set in environment!")
        print("   The agent endpoints will fail without a valid API key.")
        print("   Please set GOOGLE_API_KEY in your .env file.")
    
    print(f"🚀 SmartApply Web Agent starting...")
    print(f"   Environment: {settings.app_env}")
    print(f"   Headless mode: {settings.headless}")
    print(f"   Server: http://{settings.host}:{settings.port}")
    
    yield  # Application runs here
    
    # Shutdown
    print("👋 SmartApply Web Agent shutting down...")


# =============================================================================
# FastAPI Application Instance
# =============================================================================

app = FastAPI(
    title="SmartApply Web Agent",
    description="A web automation agent powered by Gemini 2.0 Flash and browser-use",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",      # Swagger UI at /docs
    redoc_url="/redoc",    # ReDoc at /redoc
)

# -----------------------------------------------------------------------------
# CORS Middleware (configure for your frontend domain in production)
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "SmartApply Web Agent API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    
    Returns the current status, version, and environment.
    """
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.app_env,
    )


@app.post("/agent/run", response_model=AgentTaskResponse, tags=["Agent"])
async def run_agent_task(request: AgentTaskRequest):
    """
    Execute a web automation task using the AI agent.
    
    The agent will:
    1. Launch a headless browser
    2. Use Gemini 2.0 Flash to understand and execute the task
    3. Return the results
    
    **Note**: This is a synchronous endpoint that waits for task completion.
    For long-running tasks, consider using the async endpoint.
    
    Example tasks:
    - "Go to google.com and search for 'Python tutorials'"
    - "Navigate to news.ycombinator.com and find the top story"
    - "Search for job listings on LinkedIn for 'Software Engineer'"
    """
    settings = get_settings()
    
    # Validate API key
    if not settings.google_api_key:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_API_KEY not configured. Please set it in .env file."
        )
    
    agent = None
    try:
        # Create and run agent
        agent = await create_web_agent(request.task)
        result = await agent.run()
        
        return AgentTaskResponse(
            success=True,
            task=request.task,
            result=str(result),
        )
        
    except Exception as e:
        return AgentTaskResponse(
            success=False,
            task=request.task,
            error=str(e),
        )
        
    finally:
        # Always clean up browser resources
        if agent:
            await agent.close()


# =============================================================================
# Main Entry Point (for direct execution)
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,  # Auto-reload in development only
        log_level="info",
    )
