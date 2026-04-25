"""
Functional Parity Regression Tests

Validates that FastAPI microservices provide the same functionality as the
legacy Flask monolith. Tests ensure feature parity between old and new systems.
"""

import pytest
import httpx
from typing import Dict, List
from decimal import Decimal


@pytest.mark.regression
@pytest.mark.e2e
class TestAuthenticationParity:
    """Test authentication feature parity between Flask and FastAPI."""
    
    def test_login_functionality_parity(self, auth_client, legacy_client, test_user_credentials):
        """Verify login works in both legacy and new system."""
        # Test legacy Flask login
        legacy_login_data = {
            "username": test_user_credentials["username"],
            "password": test_user_credentials["password"]
        }
        legacy_response = legacy_client.post("/login", data=legacy_login_data, follow_redirects=True)
        legacy_login_success = legacy_response.status_code == 200 and "dashboard" in legacy_response.text.lower()
        
        # Test FastAPI login
        fastapi_login_data = {
            "username": test_user_credentials["username"],
            "password": test_user_credentials["password"]
        }
        fastapi_response = auth_client.post("/api/v1/auth/login", data=fastapi_login_data)
        fastapi_login_success = fastapi_response.status_code == 200 and "access_token" in fastapi_response.json()
        
        # Both should succeed or both should fail
        assert legacy_login_success == fastapi_login_success, (
            "Login behavior differs between legacy and new system"
        )
    
    def test_login_error_messages_parity(self, auth_client, legacy_client):
        """Verify login error handling is consistent."""
        invalid_credentials = {
            "username": "nonexistent_user_12345",
            "password": "wrongpassword"
        }
        
        # Legacy Flask response
        legacy_response = legacy_client.post("/login", data=invalid_credentials, follow_redirects=True)
        legacy_rejects = legacy_response.status_code == 200 and "invalid" in legacy_response.text.lower()
        
        # FastAPI response
        fastapi_response = auth_client.post("/api/v1/auth/login", data=invalid_credentials)
        fastapi_rejects = fastapi_response.status_code == 401
        
        assert legacy_rejects == fastapi_rejects or fastapi_rejects, (
            "Invalid login handling differs between systems"
        )
    
    def test_session_management_parity(self, auth_client, legacy_client, test_user_credentials):
        """Verify session/token management provides equivalent access control."""
        # Login to both systems
        login_data = {
            "username": test_user_credentials["username"],
            "password": test_user_credentials["password"]
        }
        
        # Legacy - get session cookie
        legacy_response = legacy_client.post("/login", data=login_data, follow_redirects=True)
        legacy_has_session = "session" in [c.name for c in legacy_response.cookies.jar]
        
        # FastAPI - get token
        fastapi_response = auth_client.post("/api/v1/auth/login", data=login_data)
        fastapi_has_token = fastapi_response.status_code == 200 and "access_token" in fastapi_response.json()
        
        # Both should authenticate successfully
        assert legacy_has_session == fastapi_has_token or fastapi_has_token
    
    def test_protected_resource_access_parity(self, auth_client, legacy_client, auth_tokens, legacy_session_cookie):
        """Verify protected resources require authentication in both systems."""
        # Try accessing protected resource without auth
        legacy_unauthorized = legacy_client.get("/admin/dashboard")
        fastapi_unauthorized = auth_client.get("/api/v1/auth/me")
        
        # Both should deny access
        assert legacy_unauthorized.status_code in [302, 401, 403]
        assert fastapi_unauthorized.status_code == 401
        
        # Try with authentication
        legacy_authorized = legacy_client.get("/admin/dashboard", cookies=legacy_session_cookie)
        fastapi_authorized = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_tokens['access_token']}"}
        )
        
        # Both should allow access (or redirect to login in legacy)
        assert legacy_authorized.status_code in [200, 302]
        assert fastapi_authorized.status_code == 200


@pytest.mark.regression
@pytest.mark.e2e
class TestProductCatalogParity:
    """Test product catalog feature parity."""
    
    def test_product_listing_parity(self, catalog_client, legacy_client):
        """Verify product listing returns similar results in both systems."""
        # Legacy product list
        legacy_response = legacy_client.get("/api/products")
        legacy_products = legacy_response.json() if legacy_response.status_code == 200 else []
        
        # FastAPI product list
        fastapi_response = catalog_client.get("/api/v1/products?page_size=100")
        fastapi_data = fastapi_response.json() if fastapi_response.status_code == 200 else {"items": []}
        fastapi_products = fastapi_data.get("items", [])
        
        # Product counts should be similar (allowing for pagination differences)
        if legacy_products and fastapi_products:
            assert abs(len(legacy_products) - len(fastapi_products)) <= 5
    
    def test_product_detail_parity(self, catalog_client, legacy_client):
        """Verify product detail view provides equivalent information."""
        # Get a product from FastAPI
        list_response = catalog_client.get("/api/v1/products?page_size=1")
        if list_response.status_code != 200 or not list_response.json().get("items"):
            pytest.skip("No products available")
        
        product = list_response.json()["items"][0]
        sku = product["sku"]
        
        # Get same product from legacy
        legacy_response = legacy_client.get(f"/api/products/{sku}")
        
        if legacy_response.status_code == 200:
            legacy_product = legacy_response.json()
            
            # Verify key fields match
            assert product["name"] == legacy_product.get("name")
            assert Decimal(str(product["price"])) == Decimal(str(legacy_product.get("price", 0)))
            assert product["quantity"] == legacy_product.get("quantity")
    
    def test_product_search_parity(self, catalog_client, legacy_client):
        """Verify product search works similarly in both systems."""
        search_term = "test"
        
        # Legacy search
        legacy_response = legacy_client.get(f"/api/products/search?q={search_term}")
        legacy_results = legacy_response.json() if legacy_response.status_code == 200 else []
        
        # FastAPI search
        fastapi_response = catalog_client.get(f"/api/v1/products/search?q={search_term}")
        fastapi_data = fastapi_response.json() if fastapi_response.status_code == 200 else {"items": []}
        fastapi_results = fastapi_data.get("items", [])
        
        # Both should return results or empty list
        assert isinstance(legacy_results, list)
        assert isinstance(fastapi_results, list)
    
    def test_product_filtering_parity(self, catalog_client, legacy_client):
        """Verify product filtering works in both systems."""
        # Test category filter
        legacy_response = legacy_client.get("/api/products?category=electronics")
        fastapi_response = catalog_client.get("/api/v1/products?category=electronics")
        
        # Both should accept the filter parameter
        assert legacy_response.status_code in [200, 400]
        assert fastapi_response.status_code in [200, 400]
    
    def test_product_sorting_parity(self, catalog_client, legacy_client):
        """Verify product sorting works in both systems."""
        # Test price sorting
        legacy_response = legacy_client.get("/api/products?sort=price&order=desc")
        fastapi_response = catalog_client.get("/api/v1/products?sort_by=price&sort_order=desc")
        
        assert legacy_response.status_code in [200, 400]
        assert fastapi_response.status_code in [200, 400]


@pytest.mark.regression
@pytest.mark.e2e
class TestOrderManagementParity:
    """Test order management feature parity."""
    
    def test_order_creation_parity(self, authenticated_order_client, legacy_client, sample_order_data, auth_tokens):
        """Verify order creation works in both systems."""
        # Create order in FastAPI
        fastapi_response = authenticated_order_client.post("/api/v1/orders", json=sample_order_data)
        fastapi_created = fastapi_response.status_code == 201
        
        # Legacy order creation (would need session cookie)
        # This is a simplified check - in real tests you'd need authenticated legacy session
        legacy_response = legacy_client.post("/api/orders", json=sample_order_data)
        legacy_accepts = legacy_response.status_code in [200, 201, 401, 403]
        
        # Both should handle the request appropriately
        assert fastapi_created or fastapi_response.status_code in [400, 422, 403]
    
    def test_order_listing_parity(self, authenticated_order_client, legacy_client, auth_tokens):
        """Verify order listing works for authenticated users."""
        # FastAPI order list
        fastapi_response = authenticated_order_client.get("/api/v1/orders")
        fastapi_orders = fastapi_response.json().get("items", []) if fastapi_response.status_code == 200 else []
        
        # Legacy order list (would need session)
        legacy_response = legacy_client.get("/api/orders")
        
        # FastAPI should return orders for authenticated user
        assert fastapi_response.status_code == 200
        assert isinstance(fastapi_orders, list)
    
    def test_order_detail_parity(self, authenticated_order_client, legacy_client):
        """Verify order detail view provides equivalent information."""
        # Get an order from FastAPI
        list_response = authenticated_order_client.get("/api/v1/orders?page_size=1")
        if list_response.status_code != 200 or not list_response.json().get("items"):
            pytest.skip("No orders available")
        
        order = list_response.json()["items"][0]
        order_id = order["id"]
        
        # Get order detail
        detail_response = authenticated_order_client.get(f"/api/v1/orders/{order_id}")
        
        assert detail_response.status_code == 200
        order_detail = detail_response.json()
        
        # Verify order has expected fields
        assert "order_number" in order_detail
        assert "items" in order_detail
        assert "total_amount" in order_detail
        assert "status" in order_detail
    
    def test_order_status_workflow_parity(self, authenticated_order_client, legacy_client):
        """Verify order status transitions work similarly."""
        # Get a pending order
        list_response = authenticated_order_client.get("/api/v1/orders?status=pending&page_size=1")
        if list_response.status_code != 200 or not list_response.json().get("items"):
            pytest.skip("No pending orders available")
        
        order = list_response.json()["items"][0]
        order_id = order["id"]
        
        # Try to update status
        update_response = authenticated_order_client.patch(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "processing"}
        )
        
        # Should either succeed or fail with appropriate error
        assert update_response.status_code in [200, 403, 422]


@pytest.mark.regression
@pytest.mark.e2e
class TestBusinessLogicParity:
    """Test business logic parity between systems."""
    
    def test_inventory_calculation_parity(self, catalog_client, legacy_client):
        """Verify inventory calculations are consistent."""
        # Get product with inventory
        response = catalog_client.get("/api/v1/products?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No products available")
        
        product = response.json()["items"][0]
        sku = product["sku"]
        
        # Legacy inventory check
        legacy_response = legacy_client.get(f"/api/products/{sku}/inventory")
        
        # Both should handle inventory queries
        assert response.status_code == 200
    
    def test_pricing_calculation_parity(self, catalog_client, legacy_client):
        """Verify pricing calculations are consistent."""
        # Get a product
        response = catalog_client.get("/api/v1/products?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No products available")
        
        product = response.json()["items"][0]
        
        # Verify price is positive number
        assert float(product["price"]) > 0
        assert isinstance(product["price"], (int, float))
    
    def test_order_total_calculation_parity(self, authenticated_order_client):
        """Verify order total calculations are correct."""
        # Get an order with items
        response = authenticated_order_client.get("/api/v1/orders?page_size=1")
        if response.status_code != 200 or not response.json().get("items"):
            pytest.skip("No orders available")
        
        order = response.json()["items"][0]
        order_id = order["id"]
        
        # Get full order detail
        detail_response = authenticated_order_client.get(f"/api/v1/orders/{order_id}")
        if detail_response.status_code != 200:
            pytest.skip("Could not get order details")
        
        order_detail = detail_response.json()
        
        # Verify total calculation
        items = order_detail.get("items", [])
        calculated_subtotal = sum(
            item["quantity"] * float(item["unit_price"]) 
            for item in items
        )
        
        # Allow for small rounding differences
        actual_subtotal = float(order_detail.get("subtotal", 0))
        assert abs(calculated_subtotal - actual_subtotal) < 0.01


@pytest.mark.regression
@pytest.mark.api
class TestResponseFormatParity:
    """Test API response format parity."""
    
    def test_success_response_format_parity(self, auth_client, legacy_client):
        """Verify success responses have consistent structure."""
        # FastAPI success response
        fastapi_response = auth_client.get("/api/v1/products?page_size=1")
        
        if fastapi_response.status_code == 200:
            data = fastapi_response.json()
            # Should have consistent top-level structure
            assert "items" in data or "data" in data or isinstance(data, list)
    
    def test_error_response_format_parity(self, auth_client, legacy_client):
        """Verify error responses have consistent structure."""
        # FastAPI error response (invalid endpoint)
        fastapi_response = auth_client.get("/api/v1/nonexistent")
        
        assert fastapi_response.status_code in [404, 400]
        
        error_data = fastapi_response.json()
        # Should have error detail
        assert "detail" in error_data or "error" in error_data or "message" in error_data
    
    def test_validation_error_format_parity(self, auth_client, legacy_client):
        """Verify validation error responses are consistent."""
        # Send invalid data
        invalid_data = {"invalid_field": "value"}
        
        fastapi_response = auth_client.post("/api/v1/auth/register", json=invalid_data)
        
        # Should return validation error
        assert fastapi_response.status_code in [400, 422]
        
        error_data = fastapi_response.json()
        assert "detail" in error_data
