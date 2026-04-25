"""
API Contract Regression Tests

Validates that FastAPI microservices maintain API contracts compatible with
expected client usage. Tests request/response schemas, status codes, and
error formats.
"""

import pytest
import httpx
from typing import Dict, Any


@pytest.mark.smoke
@pytest.mark.api
class TestAuthServiceContracts:
    """Test Auth Service API contracts."""
    
    def test_register_endpoint_schema(self, auth_client):
        """Verify user registration endpoint accepts expected schema."""
        payload = {
            "username": "contract_test_user",
            "email": "contract_test@example.com",
            "password": "SecurePass123!",
            "full_name": "Contract Test User"
        }
        
        response = auth_client.post("/api/v1/auth/register", json=payload)
        
        # Should either succeed (201) or fail with validation error (422)
        assert response.status_code in [201, 422, 409]
        
        if response.status_code == 201:
            data = response.json()
            assert "id" in data
            assert "username" in data
            assert "email" in data
            assert "password" not in data  # Should never return password
    
    def test_login_endpoint_schema(self, auth_client, test_user_credentials):
        """Verify login endpoint accepts form data and returns tokens."""
        # First ensure user exists
        try:
            auth_client.post("/api/v1/auth/register", json=test_user_credentials)
        except httpx.HTTPStatusError:
            pass
        
        login_data = {
            "username": test_user_credentials["username"],
            "password": test_user_credentials["password"]
        }
        
        response = auth_client.post("/api/v1/auth/login", data=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify token response structure
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert isinstance(data["access_token"], str)
        assert len(data["access_token"]) > 0
    
    def test_login_validation_errors(self, auth_client):
        """Verify login endpoint returns proper validation errors."""
        # Missing password
        response = auth_client.post("/api/v1/auth/login", data={"username": "test"})
        assert response.status_code == 422
        
        error_data = response.json()
        assert "detail" in error_data
    
    def test_token_refresh_contract(self, auth_client, auth_tokens):
        """Verify token refresh endpoint contract."""
        if not auth_tokens.get("refresh_token"):
            pytest.skip("Refresh token not available")
        
        response = auth_client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {auth_tokens['refresh_token']}"}
        )
        
        # Should succeed or return 401 if refresh token expired
        assert response.status_code in [200, 401]
        
        if response.status_code == 200:
            data = response.json()
            assert "access_token" in data
    
    def test_current_user_endpoint(self, authenticated_auth_client):
        """Verify current user endpoint returns expected user data."""
        response = authenticated_auth_client.get("/api/v1/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "password" not in data
        assert "full_name" in data
    
    def test_unauthorized_access(self, auth_client):
        """Verify unauthorized access returns 401 with proper error format."""
        response = auth_client.get("/api/v1/auth/me")
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


@pytest.mark.smoke
@pytest.mark.api
class TestCatalogServiceContracts:
    """Test Catalog Service API contracts."""
    
    def test_products_list_endpoint(self, catalog_client):
        """Verify products list endpoint returns paginated response."""
        response = catalog_client.get("/api/v1/products")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify pagination structure
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert isinstance(data["items"], list)
    
    def test_products_list_pagination_params(self, catalog_client):
        """Verify products list accepts pagination parameters."""
        response = catalog_client.get("/api/v1/products?page=1&page_size=10")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["page_size"] == 10
    
    def test_product_detail_endpoint(self, catalog_client):
        """Verify product detail endpoint returns full product data."""
        # First get a product ID from list
        list_response = catalog_client.get("/api/v1/products?page_size=1")
        if list_response.status_code != 200 or not list_response.json()["items"]:
            pytest.skip("No products available for testing")
        
        product_id = list_response.json()["items"][0]["id"]
        
        response = catalog_client.get(f"/api/v1/products/{product_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify product structure
        assert "id" in data
        assert "sku" in data
        assert "name" in data
        assert "price" in data
        assert "quantity" in data
    
    def test_product_create_contract(self, authenticated_catalog_client, sample_product_data):
        """Verify product creation endpoint contract."""
        response = authenticated_catalog_client.post(
            "/api/v1/products",
            json=sample_product_data
        )
        
        assert response.status_code in [201, 403]  # Created or Forbidden
        
        if response.status_code == 201:
            data = response.json()
            assert "id" in data
            assert data["sku"] == sample_product_data["sku"]
            assert data["name"] == sample_product_data["name"]
    
    def test_product_update_contract(self, authenticated_catalog_client, sample_product_data):
        """Verify product update endpoint contract."""
        # First create a product
        create_response = authenticated_catalog_client.post(
            "/api/v1/products",
            json=sample_product_data
        )
        
        if create_response.status_code != 201:
            pytest.skip("Could not create test product")
        
        product_id = create_response.json()["id"]
        
        # Update the product
        update_data = {"name": "Updated Product Name", "price": 149.99}
        response = authenticated_catalog_client.patch(
            f"/api/v1/products/{product_id}",
            json=update_data
        )
        
        assert response.status_code in [200, 403]
        
        if response.status_code == 200:
            data = response.json()
            assert data["name"] == update_data["name"]
            assert data["price"] == update_data["price"]
    
    def test_product_delete_contract(self, authenticated_catalog_client, sample_product_data):
        """Verify product deletion endpoint contract."""
        # Create a product to delete
        sample_product_data["sku"] = f"DELETE-TEST-{sample_product_data['sku']}"
        create_response = authenticated_catalog_client.post(
            "/api/v1/products",
            json=sample_product_data
        )
        
        if create_response.status_code != 201:
            pytest.skip("Could not create test product")
        
        product_id = create_response.json()["id"]
        
        # Delete the product
        response = authenticated_catalog_client.delete(f"/api/v1/products/{product_id}")
        
        assert response.status_code in [204, 200, 403]
        
        # Verify product is deleted
        get_response = authenticated_catalog_client.get(f"/api/v1/products/{product_id}")
        assert get_response.status_code == 404
    
    def test_product_search_contract(self, catalog_client):
        """Verify product search endpoint contract."""
        response = catalog_client.get("/api/v1/products/search?q=test")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
    
    def test_categories_list_endpoint(self, catalog_client):
        """Verify categories list endpoint contract."""
        response = catalog_client.get("/api/v1/categories")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list) or "items" in data
        
        if isinstance(data, list) and len(data) > 0:
            category = data[0]
            assert "id" in category
            assert "name" in category
            assert "slug" in category


@pytest.mark.smoke
@pytest.mark.api
class TestOrderServiceContracts:
    """Test Order Service API contracts."""
    
    def test_orders_list_endpoint(self, authenticated_order_client):
        """Verify orders list endpoint returns paginated response."""
        response = authenticated_order_client.get("/api/v1/orders")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)
    
    def test_order_create_contract(self, authenticated_order_client, sample_order_data):
        """Verify order creation endpoint contract."""
        response = authenticated_order_client.post(
            "/api/v1/orders",
            json=sample_order_data
        )
        
        assert response.status_code in [201, 400, 422]
        
        if response.status_code == 201:
            data = response.json()
            assert "id" in data
            assert "order_number" in data
            assert data["order_number"] == sample_order_data["order_number"]
            assert "status" in data
            assert "total_amount" in data
    
    def test_order_detail_endpoint(self, authenticated_order_client):
        """Verify order detail endpoint returns full order data."""
        # Get an order from list
        list_response = authenticated_order_client.get("/api/v1/orders?page_size=1")
        if list_response.status_code != 200 or not list_response.json()["items"]:
            pytest.skip("No orders available for testing")
        
        order_id = list_response.json()["items"][0]["id"]
        
        response = authenticated_order_client.get(f"/api/v1/orders/{order_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "order_number" in data
        assert "items" in data
        assert "total_amount" in data
        assert "status" in data
    
    def test_order_status_update_contract(self, authenticated_order_client):
        """Verify order status update endpoint contract."""
        # Get an order
        list_response = authenticated_order_client.get("/api/v1/orders?page_size=1")
        if list_response.status_code != 200 or not list_response.json()["items"]:
            pytest.skip("No orders available for testing")
        
        order_id = list_response.json()["items"][0]["id"]
        
        response = authenticated_order_client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "processing"}
        )
        
        assert response.status_code in [200, 403, 422]
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data
    
    def test_order_cancel_contract(self, authenticated_order_client):
        """Verify order cancellation endpoint contract."""
        # Get a pending order
        list_response = authenticated_order_client.get("/api/v1/orders?status=pending&page_size=1")
        if list_response.status_code != 200 or not list_response.json()["items"]:
            pytest.skip("No pending orders available for testing")
        
        order_id = list_response.json()["items"][0]["id"]
        
        response = authenticated_order_client.post(f"/api/v1/orders/{order_id}/cancel")
        
        assert response.status_code in [200, 400, 403]
        
        if response.status_code == 200:
            data = response.json()
            assert data.get("status") == "cancelled"


@pytest.mark.regression
@pytest.mark.api
class TestCrossServiceContracts:
    """Test contracts between services."""
    
    def test_auth_token_validation_across_services(self, auth_client, catalog_client, order_client):
        """Verify auth tokens work across all services."""
        # Get token from auth service
        login_data = {
            "username": "testuser_regression",
            "password": "TestPass123!"
        }
        auth_response = auth_client.post("/api/v1/auth/login", data=login_data)
        
        if auth_response.status_code != 200:
            pytest.skip("Could not authenticate")
        
        token = auth_response.json()["access_token"]
        
        # Test token on catalog service
        catalog_response = catalog_client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert catalog_response.status_code == 200
        
        # Test token on order service
        order_response = order_client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert order_response.status_code == 200
    
    def test_service_health_endpoints(self, auth_client, catalog_client, order_client):
        """Verify all services have health check endpoints."""
        services = [
            ("auth", auth_client, "/health"),
            ("catalog", catalog_client, "/health"),
            ("order", order_client, "/health")
        ]
        
        for service_name, client, endpoint in services:
            response = client.get(endpoint)
            assert response.status_code == 200, f"{service_name} health check failed"
            
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "ok", "up"]
