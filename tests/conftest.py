"""
Pytest configuration and shared fixtures for InventoryTracker regression tests.

This module provides comprehensive test fixtures for:
- Database connections (PostgreSQL for FastAPI, MySQL for legacy Flask)
- HTTP clients for microservices and legacy app
- Authentication tokens and test users
- Test data factories
- Service URLs and configurations
"""

import asyncio
import os
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Generator, Optional
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

# Service URLs from environment or defaults
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://localhost:8002")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8003")
LEGACY_APP_URL = os.getenv("LEGACY_APP_URL", "http://localhost:5000")

# Database URLs
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql+asyncpg://test_user:test_pass@localhost:5433/inventory_tracker_test"
)
MYSQL_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://legacy_user:legacy_pass@localhost:3307/inventory_tracker_legacy"
)


# =============================================================================
# Event Loop and Async Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def auth_client() -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for auth service."""
    with httpx.Client(base_url=AUTH_SERVICE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def catalog_client() -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for catalog service."""
    with httpx.Client(base_url=CATALOG_SERVICE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def order_client() -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for order service."""
    with httpx.Client(base_url=ORDER_SERVICE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def legacy_client() -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for legacy Flask app."""
    with httpx.Client(base_url=LEGACY_APP_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_auth_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Asynchronous HTTP client for auth service."""
    async with httpx.AsyncClient(base_url=AUTH_SERVICE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_catalog_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Asynchronous HTTP client for catalog service."""
    async with httpx.AsyncClient(base_url=CATALOG_SERVICE_URL, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def async_order_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Asynchronous HTTP client for order service."""
    async with httpx.AsyncClient(base_url=ORDER_SERVICE_URL, timeout=30.0) as client:
        yield client


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def postgres_engine():
    """Create PostgreSQL engine for FastAPI services testing."""
    # Convert async URL to sync for setup
    sync_url = DATABASE_URL.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def postgres_sessionmaker(postgres_engine):
    """Session maker for PostgreSQL."""
    return sessionmaker(bind=postgres_engine, expire_on_commit=False)


@pytest.fixture
def postgres_session(postgres_sessionmaker) -> Generator[Session, None, None]:
    """Provide a transactional PostgreSQL session for tests."""
    session = postgres_sessionmaker()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest_asyncio.fixture(scope="session")
async def async_postgres_engine():
    """Create async PostgreSQL engine."""
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def async_postgres_sessionmaker(async_postgres_engine):
    """Async session maker for PostgreSQL."""
    return async_sessionmaker(
        bind=async_postgres_engine,
        expire_on_commit=False,
        class_=AsyncSession
    )


@pytest_asyncio.fixture
async def async_postgres_session(async_postgres_sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    """Provide an async transactional PostgreSQL session for tests."""
    async with async_postgres_sessionmaker() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture(scope="session")
def mysql_engine():
    """Create MySQL engine for legacy Flask testing."""
    engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def mysql_sessionmaker(mysql_engine):
    """Session maker for MySQL."""
    return sessionmaker(bind=mysql_engine, expire_on_commit=False)


@pytest.fixture
def mysql_session(mysql_sessionmaker) -> Generator[Session, None, None]:
    """Provide a transactional MySQL session for tests."""
    session = mysql_sessionmaker()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# Authentication Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def test_user_credentials() -> Dict[str, str]:
    """Standard test user credentials."""
    return {
        "username": "testuser_regression",
        "email": "testuser_regression@example.com",
        "password": "TestPass123!",
        "full_name": "Regression Test User"
    }


@pytest.fixture(scope="session")
def admin_user_credentials() -> Dict[str, str]:
    """Admin test user credentials."""
    return {
        "username": "admin_regression",
        "email": "admin_regression@example.com",
        "password": "AdminPass123!",
        "full_name": "Regression Admin User",
        "role": "admin"
    }


@pytest.fixture(scope="session")
def auth_tokens(auth_client, test_user_credentials) -> Dict[str, str]:
    """
    Get authentication tokens for test user.
    Creates user if doesn't exist, then logs in.
    """
    # Try to register user
    try:
        auth_client.post("/api/v1/auth/register", json=test_user_credentials)
    except httpx.HTTPStatusError:
        pass  # User may already exist
    
    # Login to get tokens
    login_data = {
        "username": test_user_credentials["username"],
        "password": test_user_credentials["password"]
    }
    response = auth_client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200, f"Failed to login: {response.text}"
    
    tokens = response.json()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer")
    }


@pytest.fixture
def authenticated_auth_client(auth_client, auth_tokens) -> httpx.Client:
    """Auth client with authentication headers."""
    auth_client.headers["Authorization"] = f"Bearer {auth_tokens['access_token']}"
    return auth_client


@pytest.fixture
def authenticated_catalog_client(catalog_client, auth_tokens) -> httpx.Client:
    """Catalog client with authentication headers."""
    catalog_client.headers["Authorization"] = f"Bearer {auth_tokens['access_token']}"
    return catalog_client


@pytest.fixture
def authenticated_order_client(order_client, auth_tokens) -> httpx.Client:
    """Order client with authentication headers."""
    order_client.headers["Authorization"] = f"Bearer {auth_tokens['access_token']}"
    return order_client


@pytest_asyncio.fixture(scope="session")
async def async_auth_tokens(async_auth_client, test_user_credentials) -> Dict[str, str]:
    """Async authentication tokens for test user."""
    # Try to register user
    try:
        await async_auth_client.post("/api/v1/auth/register", json=test_user_credentials)
    except httpx.HTTPStatusError:
        pass
    
    login_data = {
        "username": test_user_credentials["username"],
        "password": test_user_credentials["password"]
    }
    response = await async_auth_client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    
    tokens = response.json()
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer")
    }


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture
def sample_product_data() -> Dict:
    """Sample product data for testing."""
    return {
        "sku": f"TEST-SKU-{uuid4().hex[:8].upper()}",
        "name": "Test Product",
        "description": "A test product for regression testing",
        "category": "test_category",
        "price": 99.99,
        "cost": 49.99,
        "quantity": 100,
        "min_stock_level": 10,
        "max_stock_level": 500,
        "unit_of_measure": "piece",
        "status": "active",
        "attributes": {
            "color": "blue",
            "size": "medium",
            "weight": "1.5kg"
        },
        "supplier_id": None,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_order_data() -> Dict:
    """Sample order data for testing."""
    return {
        "order_number": f"ORD-{uuid4().hex[:12].upper()}",
        "customer_id": str(uuid4()),
        "customer_email": "customer@example.com",
        "status": "pending",
        "items": [
            {
                "product_id": str(uuid4()),
                "sku": "TEST-SKU-001",
                "quantity": 2,
                "unit_price": 99.99,
                "total_price": 199.98
            }
        ],
        "subtotal": 199.98,
        "tax_amount": 16.00,
        "shipping_amount": 10.00,
        "total_amount": 225.98,
        "shipping_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip": "12345",
            "country": "US"
        },
        "billing_address": {
            "street": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zip": "12345",
            "country": "US"
        },
        "payment_method": "credit_card",
        "notes": "Test order for regression testing",
        "created_at": datetime.utcnow().isoformat()
    }


@pytest.fixture
def sample_category_data() -> Dict:
    """Sample category data for testing."""
    return {
        "name": f"Test Category {uuid4().hex[:6]}",
        "slug": f"test-category-{uuid4().hex[:6]}",
        "description": "A test category for regression testing",
        "parent_id": None,
        "sort_order": 0,
        "is_active": True,
        "metadata": {
            "display_type": "grid",
            "featured": False
        }
    }


# =============================================================================
# Legacy App Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def legacy_session_cookie(legacy_client, test_user_credentials) -> Dict[str, str]:
    """Get session cookie from legacy Flask app."""
    # Login to legacy app
    login_data = {
        "username": test_user_credentials["username"],
        "password": test_user_credentials["password"]
    }
    response = legacy_client.post("/login", data=login_data, follow_redirects=True)
    
    if response.status_code == 200:
        # Extract session cookie
        cookies = response.cookies
        return dict(cookies)
    
    # If login fails, return empty (some tests may not require auth)
    return {}


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def api_response_validator():
    """Validator for API responses."""
    class Validator:
        @staticmethod
        def validate_success(response: httpx.Response, expected_status: int = 200):
            """Validate successful API response."""
            assert response.status_code == expected_status, (
                f"Expected status {expected_status}, got {response.status_code}. "
                f"Response: {response.text}"
            )
            data = response.json()
            assert "data" in data or "id" in data or "success" in data, (
                f"Response missing expected fields: {data}"
            )
            return data
        
        @staticmethod
        def validate_error(response: httpx.Response, expected_status: int):
            """Validate error API response."""
            assert response.status_code == expected_status
            data = response.json()
            assert "detail" in data or "error" in data or "message" in data
            return data
        
        @staticmethod
        def validate_pagination(response: httpx.Response):
            """Validate paginated response structure."""
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "total_pages" in data
            return data
    
    return Validator()


@pytest.fixture
def data_comparator():
    """Comparator for data validation between legacy and new systems."""
    from deepdiff import DeepDiff
    
    class Comparator:
        @staticmethod
        def compare_products(legacy_product: Dict, new_product: Dict, 
                            ignore_fields: Optional[list] = None) -> Dict:
            """Compare product data between legacy and new system."""
            ignore = ignore_fields or ["id", "created_at", "updated_at", "_id"]
            
            # Normalize field names
            legacy_normalized = {k.lower().replace("_", ""): v 
                               for k, v in legacy_product.items()}
            new_normalized = {k.lower().replace("_", ""): v 
                            for k, v in new_product.items()}
            
            diff = DeepDiff(legacy_normalized, new_normalized, 
                          ignore_order=True, 
                          exclude_paths=ignore)
            return diff
        
        @staticmethod
        def compare_orders(legacy_order: Dict, new_order: Dict,
                          ignore_fields: Optional[list] = None) -> Dict:
            """Compare order data between legacy and new system."""
            ignore = ignore_fields or ["id", "created_at", "updated_at", "_id"]
            
            diff = DeepDiff(legacy_order, new_order,
                          ignore_order=True,
                          exclude_paths=ignore)
            return diff
    
    return Comparator()


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_test_data(postgres_session):
    """Automatically clean up test data after each test."""
    yield
    # Cleanup will be handled by transaction rollback in postgres_session fixture
    pass
