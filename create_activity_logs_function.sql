-- SQL function to fetch activity logs
-- Run this in your PostgreSQL database

CREATE OR REPLACE FUNCTION get_activity_logs()
RETURNS TABLE (
    id INTEGER,
    user_id INTEGER,
    username VARCHAR,
    action VARCHAR,
    details TEXT,
    ip_address VARCHAR,
    created_at TIMESTAMP
) AS $$
BEGIN
    -- Adjust this query based on your actual activity_logs table structure
    RETURN QUERY
    SELECT 
        al.id,
        al.user_id,
        u.username,
        al.action,
        al.details,
        al.ip_address,
        al.created_at
    FROM activity_logs al
    LEFT JOIN users u ON al.user_id = u.id
    ORDER BY al.created_at DESC
    LIMIT 100;
END;
$$ LANGUAGE plpgsql;
