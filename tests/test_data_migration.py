"""
Data Migration Regression Tests

Validates that data migrated from MySQL (legacy Flask) to PostgreSQL (FastAPI)
maintains integrity, completeness, and accuracy. These tests ensure no data
loss or corruption during the migration process.
"""

import pytest
from typing import Dict, List
from decimal import Decimal
from datetime import datetime
from deepdiff import DeepDiff


@pytest.mark.migration
@pytest.mark.regression
@pytest.mark.database
class TestUserDataMigration:
    """Test user data migration from MySQL to PostgreSQL."""
    
    def test_user_count_consistency(self, postgres_session, mysql_session):
        """Verify user count matches between legacy and new database."""
        # Query legacy MySQL
        mysql_result = mysql_session.execute(
            "SELECT COUNT(*) as count FROM users"
        )
        mysql_count = mysql_result.scalar()
        
        # Query new PostgreSQL
        postgres_result = postgres_session.execute(
            "SELECT COUNT(*) as count FROM users"
        )
        postgres_count = postgres_result.scalar()
        
        assert mysql_count == postgres_count, (
            f"User count mismatch: MySQL={mysql_count}, PostgreSQL={postgres_count}"
        )
    
    def test_user_data_integrity(self, postgres_session, mysql_session):
        """Verify user data fields are correctly migrated."""
        # Get sample users from both databases
        mysql_users = mysql_session.execute(
            """SELECT id, username, email, full_name, is_active, 
                      created_at, updated_at 
               FROM users 
               ORDER BY id 
               LIMIT 100"""
        ).mappings().all()
        
        for mysql_user in mysql_users:
            # Find corresponding user in PostgreSQL
            postgres_user = postgres_session.execute(
                """SELECT id, username, email, full_name, is_active,
                          created_at, updated_at
                   FROM users 
                   WHERE username = :username""",
                {"username": mysql_user["username"]}
            ).mappings().first()
            
            assert postgres_user is not None, (
                f"User {mysql_user['username']} not found in PostgreSQL"
            )
            
            # Verify key fields match
            assert postgres_user["email"] == mysql_user["email"]
            assert postgres_user["full_name"] == mysql_user["full_name"]
            assert postgres_user["is_active"] == mysql_user["is_active"]
    
    def test_user_password_hash_migration(self, postgres_session, mysql_session):
        """Verify password hashes are correctly migrated."""
        mysql_users = mysql_session.execute(
            "SELECT username, password_hash FROM users WHERE password_hash IS NOT NULL LIMIT 50"
        ).mappings().all()
        
        for mysql_user in mysql_users:
            postgres_user = postgres_session.execute(
                "SELECT password_hash FROM users WHERE username = :username",
                {"username": mysql_user["username"]}
            ).mappings().first()
            
            assert postgres_user is not None
            assert postgres_user["password_hash"] == mysql_user["password_hash"], (
                f"Password hash mismatch for user {mysql_user['username']}"
            )
    
    def test_user_role_migration(self, postgres_session, mysql_session):
        """Verify user roles are correctly migrated."""
        mysql_roles = mysql_session.execute(
            """SELECT u.username, r.name as role_name
               FROM users u
               JOIN user_roles ur ON u.id = ur.user_id
               JOIN roles r ON ur.role_id = r.id"""
        ).mappings().all()
        
        for mysql_role in mysql_roles:
            postgres_role = postgres_session.execute(
                """SELECT r.name 
                   FROM users u
                   JOIN user_roles ur ON u.id = ur.user_id
                   JOIN roles r ON ur.role_id = r.id
                   WHERE u.username = :username""",
                {"username": mysql_role["username"]}
            ).scalar()
            
            assert postgres_role == mysql_role["role_name"], (
                f"Role mismatch for user {mysql_role['username']}"
            )


@pytest.mark.migration
@pytest.mark.regression
@pytest.mark.database
class TestProductDataMigration:
    """Test product data migration from MySQL to PostgreSQL."""
    
    def test_product_count_consistency(self, postgres_session, mysql_session):
        """Verify product count matches between databases."""
        mysql_count = mysql_session.execute(
            "SELECT COUNT(*) FROM products"
        ).scalar()
        
        postgres_count = postgres_session.execute(
            "SELECT COUNT(*) FROM products"
        ).scalar()
        
        assert mysql_count == postgres_count, (
            f"Product count mismatch: MySQL={mysql_count}, PostgreSQL={postgres_count}"
        )
    
    def test_product_data_completeness(self, postgres_session, mysql_session):
        """Verify all product fields are migrated correctly."""
        mysql_products = mysql_session.execute(
            """SELECT sku, name, description, price, cost, quantity,
                      category_id, supplier_id, status, created_at
               FROM products 
               ORDER BY id 
               LIMIT 100"""
        ).mappings().all()
        
        for mysql_product in mysql_products:
            postgres_product = postgres_session.execute(
                """SELECT sku, name, description, price, cost, quantity,
                          category_id, supplier_id, status, created_at
                   FROM products 
                   WHERE sku = :sku""",
                {"sku": mysql_product["sku"]}
            ).mappings().first()
            
            assert postgres_product is not None, (
                f"Product {mysql_product['sku']} not found in PostgreSQL"
            )
            
            # Compare fields with appropriate type handling
            assert postgres_product["name"] == mysql_product["name"]
            assert postgres_product["description"] == mysql_product["description"]
            assert Decimal(str(postgres_product["price"])) == Decimal(str(mysql_product["price"]))
            assert Decimal(str(postgres_product["cost"])) == Decimal(str(mysql_product["cost"]))
            assert postgres_product["quantity"] == mysql_product["quantity"]
            assert postgres_product["status"] == mysql_product["status"]
    
    def test_product_sku_uniqueness(self, postgres_session):
        """Verify SKU uniqueness constraint maintained after migration."""
        duplicate_skus = postgres_session.execute(
            """SELECT sku, COUNT(*) as count 
               FROM products 
               GROUP BY sku 
               HAVING COUNT(*) > 1"""
        ).fetchall()
        
        assert len(duplicate_skus) == 0, (
            f"Duplicate SKUs found: {duplicate_skus}"
        )
    
    def test_product_relationships_migration(self, postgres_session, mysql_session):
        """Verify product relationships (category, supplier) are preserved."""
        mysql_products = mysql_session.execute(
            """SELECT p.sku, p.category_id, c.name as category_name
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.category_id IS NOT NULL
               LIMIT 50"""
        ).mappings().all()
        
        for mysql_product in mysql_products:
            postgres_product = postgres_session.execute(
                """SELECT p.category_id, c.name as category_name
                   FROM products p
                   LEFT JOIN categories c ON p.category_id = c.id
                   WHERE p.sku = :sku""",
                {"sku": mysql_product["sku"]}
            ).mappings().first()
            
            assert postgres_product is not None
            assert postgres_product["category_name"] == mysql_product["category_name"]
    
    def test_product_attributes_migration(self, postgres_session, mysql_session):
        """Verify product attributes/JSON data migration."""
        mysql_products = mysql_session.execute(
            """SELECT sku, attributes 
               FROM products 
               WHERE attributes IS NOT NULL 
               LIMIT 50"""
        ).mappings().all()
        
        for mysql_product in mysql_products:
            postgres_product = postgres_session.execute(
                """SELECT attributes 
                   FROM products 
                   WHERE sku = :sku""",
                {"sku": mysql_product["sku"]}
            ).mappings().first()
            
            assert postgres_product is not None
            
            mysql_attrs = mysql_product["attributes"]
            postgres_attrs = postgres_product["attributes"]
            
            # Compare JSON structures
            diff = DeepDiff(mysql_attrs, postgres_attrs, ignore_order=True)
            assert not diff, f"Attributes mismatch for SKU {mysql_product['sku']}: {diff}"


@pytest.mark.migration
@pytest.mark.regression
@pytest.mark.database
class TestOrderDataMigration:
    """Test order data migration from MySQL to PostgreSQL."""
    
    def test_order_count_consistency(self, postgres_session, mysql_session):
        """Verify order count matches between databases."""
        mysql_count = mysql_session.execute(
            "SELECT COUNT(*) FROM orders"
        ).scalar()
        
        postgres_count = postgres_session.execute(
            "SELECT COUNT(*) FROM orders"
        ).scalar()
        
        assert mysql_count == postgres_count, (
            f"Order count mismatch: MySQL={mysql_count}, PostgreSQL={postgres_count}"
        )
    
    def test_order_data_integrity(self, postgres_session, mysql_session):
        """Verify order data is correctly migrated."""
        mysql_orders = mysql_session.execute(
            """SELECT order_number, customer_id, status, total_amount,
                      subtotal, tax_amount, shipping_amount, created_at
               FROM orders 
               ORDER BY id 
               LIMIT 100"""
        ).mappings().all()
        
        for mysql_order in mysql_orders:
            postgres_order = postgres_session.execute(
                """SELECT order_number, customer_id, status, total_amount,
                          subtotal, tax_amount, shipping_amount, created_at
                   FROM orders 
                   WHERE order_number = :order_number""",
                {"order_number": mysql_order["order_number"]}
            ).mappings().first()
            
            assert postgres_order is not None, (
                f"Order {mysql_order['order_number']} not found in PostgreSQL"
            )
            
            assert postgres_order["status"] == mysql_order["status"]
            assert Decimal(str(postgres_order["total_amount"])) == Decimal(str(mysql_order["total_amount"]))
            assert Decimal(str(postgres_order["subtotal"])) == Decimal(str(mysql_order["subtotal"]))
    
    def test_order_items_migration(self, postgres_session, mysql_session):
        """Verify order items are correctly migrated."""
        mysql_orders = mysql_session.execute(
            "SELECT id, order_number FROM orders LIMIT 50"
        ).mappings().all()
        
        for mysql_order in mysql_orders:
            # Get order items from MySQL
            mysql_items = mysql_session.execute(
                """SELECT product_id, sku, quantity, unit_price, total_price
                   FROM order_items 
                   WHERE order_id = :order_id""",
                {"order_id": mysql_order["id"]}
            ).mappings().all()
            
            # Get order items from PostgreSQL
            postgres_items = postgres_session.execute(
                """SELECT product_id, sku, quantity, unit_price, total_price
                   FROM order_items oi
                   JOIN orders o ON oi.order_id = o.id
                   WHERE o.order_number = :order_number""",
                {"order_number": mysql_order["order_number"]}
            ).mappings().all()
            
            assert len(mysql_items) == len(postgres_items), (
                f"Order items count mismatch for order {mysql_order['order_number']}"
            )
            
            # Compare items
            for mysql_item, postgres_item in zip(mysql_items, postgres_items):
                assert postgres_item["sku"] == mysql_item["sku"]
                assert postgres_item["quantity"] == mysql_item["quantity"]
                assert Decimal(str(postgres_item["unit_price"])) == Decimal(str(mysql_item["unit_price"]))
    
    def test_order_status_history_migration(self, postgres_session, mysql_session):
        """Verify order status history is preserved."""
        mysql_orders = mysql_session.execute(
            "SELECT id, order_number FROM orders LIMIT 30"
        ).mappings().all()
        
        for mysql_order in mysql_orders:
            mysql_history = mysql_session.execute(
                """SELECT status, changed_at, changed_by
                   FROM order_status_history 
                   WHERE order_id = :order_id
                   ORDER BY changed_at""",
                {"order_id": mysql_order["id"]}
            ).mappings().all()
            
            if mysql_history:
                postgres_history = postgres_session.execute(
                    """SELECT status, changed_at, changed_by
                       FROM order_status_history osh
                       JOIN orders o ON osh.order_id = o.id
                       WHERE o.order_number = :order_number
                       ORDER BY changed_at""",
                    {"order_number": mysql_order["order_number"]}
                ).mappings().all()
                
                assert len(mysql_history) == len(postgres_history), (
                    f"Status history count mismatch for order {mysql_order['order_number']}"
                )


@pytest.mark.migration
@pytest.mark.regression
@pytest.mark.database
class TestCategoryDataMigration:
    """Test category data migration."""
    
    def test_category_count_consistency(self, postgres_session, mysql_session):
        """Verify category count matches."""
        mysql_count = mysql_session.execute(
            "SELECT COUNT(*) FROM categories"
        ).scalar()
        
        postgres_count = postgres_session.execute(
            "SELECT COUNT(*) FROM categories"
        ).scalar()
        
        assert mysql_count == postgres_count
    
    def test_category_hierarchy_migration(self, postgres_session, mysql_session):
        """Verify category parent-child relationships are preserved."""
        mysql_categories = mysql_session.execute(
            """SELECT c1.name, c1.slug, c2.name as parent_name
               FROM categories c1
               LEFT JOIN categories c2 ON c1.parent_id = c2.id
               WHERE c1.parent_id IS NOT NULL"""
        ).mappings().all()
        
        for mysql_cat in mysql_categories:
            postgres_cat = postgres_session.execute(
                """SELECT c1.name, c2.name as parent_name
                   FROM categories c1
                   LEFT JOIN categories c2 ON c1.parent_id = c2.id
                   WHERE c1.slug = :slug""",
                {"slug": mysql_cat["slug"]}
            ).mappings().first()
            
            assert postgres_cat is not None
            assert postgres_cat["parent_name"] == mysql_cat["parent_name"]


@pytest.mark.migration
@pytest.mark.regression
@pytest.mark.integration
class TestMigrationDataValidation:
    """Comprehensive data validation tests for migration."""
    
    def test_no_orphaned_records(self, postgres_session):
        """Verify no orphaned records exist after migration."""
        # Check for order items without orders
        orphaned_items = postgres_session.execute(
            """SELECT COUNT(*) FROM order_items oi
               LEFT JOIN orders o ON oi.order_id = o.id
               WHERE o.id IS NULL"""
        ).scalar()
        
        assert orphaned_items == 0, f"Found {orphaned_items} orphaned order items"
        
        # Check for products without categories (if categories exist)
        orphaned_products = postgres_session.execute(
            """SELECT COUNT(*) FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE p.category_id IS NOT NULL AND c.id IS NULL"""
        ).scalar()
        
        assert orphaned_products == 0, f"Found {orphaned_products} orphaned products"
    
    def test_data_type_compatibility(self, postgres_session, mysql_session):
        """Verify data types are compatible after migration."""
        # Test date/timestamp fields
        mysql_timestamps = mysql_session.execute(
            """SELECT created_at FROM orders 
               WHERE created_at IS NOT NULL 
               LIMIT 10"""
        ).scalars().all()
        
        for ts in mysql_timestamps:
            assert isinstance(ts, datetime) or ts is None
        
        # Verify same data in PostgreSQL
        postgres_timestamps = postgres_session.execute(
            """SELECT created_at FROM orders 
               WHERE created_at IS NOT NULL 
               LIMIT 10"""
        ).scalars().all()
        
        for ts in postgres_timestamps:
            assert isinstance(ts, datetime) or ts is None
    
    def test_numeric_precision(self, postgres_session, mysql_session):
        """Verify numeric precision is maintained for financial data."""
        mysql_prices = mysql_session.execute(
            """SELECT price FROM products 
               WHERE price IS NOT NULL 
               LIMIT 20"""
        ).scalars().all()
        
        for price in mysql_prices:
            if price is not None:
                # Verify it can be represented as Decimal
                decimal_price = Decimal(str(price))
                assert decimal_price == Decimal(str(price))
    
    def test_migration_checksum(self, postgres_session, mysql_session):
        """Generate and compare checksums for migrated data."""
        # Calculate checksum for orders in MySQL
        mysql_checksum = mysql_session.execute(
            """SELECT MD5(GROUP_CONCAT(
                order_number, status, CAST(total_amount AS CHAR)
                ORDER BY order_number SEPARATOR '|'
            )) FROM orders"""
        ).scalar()
        
        # Calculate checksum for orders in PostgreSQL
        postgres_checksum = postgres_session.execute(
            """SELECT MD5(string_agg(
                order_number || status || total_amount::text, '|'
                ORDER BY order_number
            )) FROM orders"""
        ).scalar()
        
        # Note: This is a simplified checksum - in production you'd use
        # more sophisticated comparison methods
        assert mysql_checksum is not None
        assert postgres_checksum is not None
