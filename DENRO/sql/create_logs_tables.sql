-- SQL Script to create authentication_logs and activity_logs tables
-- Run this in your PostgreSQL database

-- Create authentication_logs table
CREATE TABLE IF NOT EXISTS authentication_logs (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auth_logs_username ON authentication_logs(username);
CREATE INDEX IF NOT EXISTS idx_auth_logs_timestamp ON authentication_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_auth_logs_status ON authentication_logs(status);

-- Create activity_logs table
CREATE TABLE IF NOT EXISTS activity_logs (
    id SERIAL PRIMARY KEY,
    task VARCHAR(255) NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_timestamp ON activity_logs(timestamp);

-- Add status column to users table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'status'
    ) THEN
        ALTER TABLE users ADD COLUMN status VARCHAR(50) DEFAULT 'active';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
