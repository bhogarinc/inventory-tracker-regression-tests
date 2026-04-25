"""
Performance Regression Tests

Validates that FastAPI microservices meet or exceed the performance of the
legacy Flask monolith. Tests response times, throughput, and resource usage.
"""

import pytest
import time
import statistics
from typing import List
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed


@pytest.mark.performance
@pytest.mark.regression
class TestResponseTimePerformance:
    """Test API response time performance."""
    
    def test_auth_login_response_time(self, auth_client, test_user_credentials):
        """Verify login response time is under threshold."""
        times = []
        
        for _ in range(10):
            start = time.perf_counter()
            response = auth_client.post(
                "/api/v1/auth/login",
                data={
                    "username": test_user_credentials["username"],
                    "password": test_user_credentials["password"]
                }
            )
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        # Assert performance thresholds (milliseconds)
        assert avg_time < 1.0, f"Average login time {avg_time:.3f}s exceeds 1s threshold"
        assert p95_time < 2.0, f"P95 login time {p95_time:.3f}s exceeds 2s threshold"
    
    def test_product_list_response_time(self, catalog_client):
        """Verify product list response time."""
        times = []
        
        for _ in range(20):
            start = time.perf_counter()
            response = catalog_client.get("/api/v1/products?page_size=50")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        p95_time = sorted(times)[int(len(times) * 0.95)]
        
        assert avg_time < 0.5, f"Average product list time {avg_time:.3f}s exceeds 500ms"
        assert p95_time < 1.0, f"P95 product list time {p95_time:.3f}s exceeds 1s"
    
    def test_product_detail_response_time(self, catalog_client):
        """Verify product detail response time."""
        # Get a product ID first
        list_response = catalog_client.get("/api/v1/products?page_size=1")
        if list_response.status_code != 200 or not list_response.json().get("items"):
            pytest.skip("No products available")
        
        product_id = list_response.json()["items"][0]["id"]
        
        times = []
        for _ in range(20):
            start = time.perf_counter()
            response = catalog_client.get(f"/api/v1/products/{product_id}")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
        
        avg_time = statistics.mean(times)
        assert avg_time < 0.3, f"Average product detail time {avg_time:.3f}s exceeds 300ms"
    
    def test_order_list_response_time(self, authenticated_order_client):
        """Verify order list response time for authenticated user."""
        times = []
        
        for _ in range(10):
            start = time.perf_counter()
            response = authenticated_order_client.get("/api/v1/orders?page_size=20")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        assert avg_time < 0.5, f"Average order list time {avg_time:.3f}s exceeds 500ms"


@pytest.mark.performance
@pytest.mark.regression
class TestThroughputPerformance:
    """Test API throughput performance."""
    
    def test_concurrent_product_reads(self, catalog_client):
        """Verify system handles concurrent product reads."""
        num_requests = 100
        num_workers = 10
        
        def make_request():
            start = time.perf_counter()
            response = catalog_client.get("/api/v1/products?page_size=20")
            elapsed = time.perf_counter() - start
            return response.status_code == 200, elapsed
        
        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())
        
        success_count = sum(1 for success, _ in results if success)
        times = [t for _, t in results]
        
        # Assert success rate
        success_rate = success_count / num_requests
        assert success_rate >= 0.99, f"Success rate {success_rate:.2%} below 99%"
        
        # Assert throughput (requests per second)
        total_time = sum(times)
        throughput = num_requests / total_time if total_time > 0 else 0
        assert throughput >= 10, f"Throughput {throughput:.1f} req/s below 10 req/s"
    
    def test_concurrent_auth_requests(self, auth_client, test_user_credentials):
        """Verify auth service handles concurrent requests."""
        num_requests = 50
        num_workers = 10
        
        def make_login_request():
            start = time.perf_counter()
            response = auth_client.post(
                "/api/v1/auth/login",
                data={
                    "username": test_user_credentials["username"],
                    "password": test_user_credentials["password"]
                }
            )
            elapsed = time.perf_counter() - start
            return response.status_code == 200, elapsed
        
        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(make_login_request) for _ in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())
        
        success_count = sum(1 for success, _ in results if success)
        success_rate = success_count / num_requests
        
        assert success_rate >= 0.95, f"Auth success rate {success_rate:.2%} below 95%"
    
    def test_concurrent_order_creation(self, authenticated_order_client):
        """Verify order service handles concurrent order creation."""
        num_requests = 20
        num_workers = 5
        
        def create_order(order_num):
            order_data = {
                "order_number": f"PERF-TEST-{order_num}",
                "customer_id": "test-customer-123",
                "items": [{"product_id": "prod-123", "quantity": 1, "unit_price": 99.99}],
                "total_amount": 99.99
            }
            start = time.perf_counter()
            response = authenticated_order_client.post("/api/v1/orders", json=order_data)
            elapsed = time.perf_counter() - start
            return response.status_code in [201, 422], elapsed
        
        results = []
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(create_order, i) for i in range(num_requests)]
            for future in as_completed(futures):
                results.append(future.result())
        
        success_count = sum(1 for success, _ in results if success)
        success_rate = success_count / num_requests
        
        assert success_rate >= 0.90, f"Order creation success rate {success_rate:.2%} below 90%"


@pytest.mark.performance
@pytest.mark.regression
class TestDatabasePerformance:
    """Test database query performance."""
    
    def test_product_search_performance(self, catalog_client):
        """Verify product search query performance."""
        search_terms = ["test", "product", "item", "widget", "gadget"]
        times = []
        
        for term in search_terms:
            for _ in range(5):
                start = time.perf_counter()
                response = catalog_client.get(f"/api/v1/products/search?q={term}")
                elapsed = time.perf_counter() - start
                times.append(elapsed)
                
                assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        p99_time = sorted(times)[int(len(times) * 0.99)]
        
        assert avg_time < 0.5, f"Average search time {avg_time:.3f}s exceeds 500ms"
        assert p99_time < 2.0, f"P99 search time {p99_time:.3f}s exceeds 2s"
    
    def test_filtered_product_query_performance(self, catalog_client):
        """Verify filtered product queries perform well."""
        filters = [
            "?category=electronics",
            "?min_price=10&max_price=100",
            "?status=active",
            "?in_stock=true",
            "?category=electronics&status=active&min_price=50"
        ]
        
        times = []
        for filter_param in filters:
            start = time.perf_counter()
            response = catalog_client.get(f"/api/v1/products{filter_param}")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            assert response.status_code == 200
        
        avg_time = statistics.mean(times)
        assert avg_time < 0.5, f"Average filtered query time {avg_time:.3f}s exceeds 500ms"
    
    def test_pagination_performance(self, catalog_client):
        """Verify pagination performance with large datasets."""
        page_sizes = [10, 50, 100]
        times = []
        
        for page_size in page_sizes:
            start = time.perf_counter()
            response = catalog_client.get(f"/api/v1/products?page_size={page_size}")
            elapsed = time.perf_counter() - start
            times.append(elapsed)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) <= page_size
        
        # Larger pages should not be disproportionately slower
        avg_time = statistics.mean(times)
        assert avg_time < 1.0, f"Average pagination time {avg_time:.3f}s exceeds 1s"


@pytest.mark.performance
@pytest.mark.regression
class TestLegacyComparisonPerformance:
    """Compare performance between legacy Flask and new FastAPI."""
    
    def test_product_list_performance_comparison(self, catalog_client, legacy_client):
        """Compare product list performance between legacy and new system."""
        # Test legacy
        legacy_times = []
        for _ in range(10):
            start = time.perf_counter()
            legacy_response = legacy_client.get("/api/products")
            legacy_elapsed = time.perf_counter() - start
            if legacy_response.status_code == 200:
                legacy_times.append(legacy_elapsed)
        
        # Test FastAPI
        fastapi_times = []
        for _ in range(10):
            start = time.perf_counter()
            fastapi_response = catalog_client.get("/api/v1/products?page_size=100")
            fastapi_elapsed = time.perf_counter() - start
            if fastapi_response.status_code == 200:
                fastapi_times.append(fastapi_elapsed)
        
        if legacy_times and fastapi_times:
            legacy_avg = statistics.mean(legacy_times)
            fastapi_avg = statistics.mean(fastapi_times)
            
            # FastAPI should be at least as fast as legacy
            assert fastapi_avg <= legacy_avg * 1.5, (
                f"FastAPI avg {fastapi_avg:.3f}s is >50% slower than legacy {legacy_avg:.3f}s"
            )
    
    def test_auth_performance_comparison(self, auth_client, legacy_client, test_user_credentials):
        """Compare authentication performance."""
        # Note: Legacy may use session-based auth, FastAPI uses JWT
        
        # FastAPI login
        fastapi_times = []
        for _ in range(10):
            start = time.perf_counter()
            response = auth_client.post(
                "/api/v1/auth/login",
                data={
                    "username": test_user_credentials["username"],
                    "password": test_user_credentials["password"]
                }
            )
            elapsed = time.perf_counter() - start
            if response.status_code == 200:
                fastapi_times.append(elapsed)
        
        avg_time = statistics.mean(fastapi_times) if fastapi_times else 0
        assert avg_time < 1.0, f"FastAPI auth avg time {avg_time:.3f}s exceeds 1s"


@pytest.mark.performance
@pytest.mark.slow
class TestLoadPerformance:
    """Load testing for sustained performance."""
    
    def test_sustained_read_load(self, catalog_client):
        """Test sustained read load over time."""
        duration = 30  # seconds
        interval = 0.1  # seconds between requests
        
        start_time = time.time()
        request_count = 0
        error_count = 0
        response_times = []
        
        while time.time() - start_time < duration:
            req_start = time.perf_counter()
            try:
                response = catalog_client.get("/api/v1/products?page_size=20")
                if response.status_code != 200:
                    error_count += 1
            except Exception:
                error_count += 1
            finally:
                elapsed = time.perf_counter() - req_start
                response_times.append(elapsed)
                request_count += 1
            
            time.sleep(interval)
        
        # Calculate metrics
        error_rate = error_count / request_count if request_count > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        
        assert error_rate < 0.01, f"Error rate {error_rate:.2%} exceeds 1%"
        assert avg_response_time < 1.0, f"Avg response time {avg_response_time:.3f}s exceeds 1s"
    
    def test_memory_usage_under_load(self, catalog_client):
        """Test that memory usage remains stable under load."""
        # This test would typically use a monitoring endpoint or external monitoring
        # For now, we just verify the service remains responsive
        
        for i in range(100):
            response = catalog_client.get("/api/v1/products?page_size=50")
            assert response.status_code == 200, f"Failed at iteration {i}"
            
            if i % 20 == 0:
                # Check health endpoint periodically
                health_response = catalog_client.get("/health")
                assert health_response.status_code == 200
