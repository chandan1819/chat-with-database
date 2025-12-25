-- PostgreSQL Test Database Setup Script
-- Run this script to create the test database and tables

-- Create database and user (run as postgres superuser)
-- CREATE DATABASE testdb;
-- CREATE USER testuser WITH PASSWORD 'testpass';
-- GRANT ALL PRIVILEGES ON DATABASE testdb TO testuser;

-- Connect to testdb and run the following:

-- Create test tables
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE,
    age INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10,2),
    category VARCHAR(100),
    in_stock BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER DEFAULT 1,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending'
);

-- Insert sample data
INSERT INTO users (name, email, age) VALUES
    ('John Doe', 'john@example.com', 28),
    ('Jane Smith', 'jane@example.com', 32),
    ('Bob Johnson', 'bob@example.com', 45),
    ('Alice Brown', 'alice@example.com', 29),
    ('Charlie Wilson', 'charlie@example.com', 38)
ON CONFLICT (email) DO NOTHING;

INSERT INTO products (name, price, category, in_stock) VALUES
    ('Laptop', 999.99, 'Electronics', true),
    ('Mouse', 29.99, 'Electronics', true),
    ('Keyboard', 79.99, 'Electronics', true),
    ('Monitor', 299.99, 'Electronics', false),
    ('Desk Chair', 199.99, 'Furniture', true),
    ('Coffee Mug', 12.99, 'Kitchen', true)
ON CONFLICT DO NOTHING;

INSERT INTO orders (user_id, product_id, quantity, status) VALUES
    (1, 1, 1, 'completed'),
    (1, 2, 2, 'completed'),
    (2, 3, 1, 'pending'),
    (3, 1, 1, 'shipped'),
    (4, 5, 1, 'completed'),
    (5, 6, 3, 'pending')
ON CONFLICT DO NOTHING;

-- Grant permissions to testuser
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO testuser;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO testuser;

-- Show what we created
SELECT 'Tables created:' as info;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

SELECT 'Sample data counts:' as info;
SELECT 'users' as table_name, COUNT(*) as row_count FROM users
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'orders', COUNT(*) FROM orders;