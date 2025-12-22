# Database Setup Instructions

## Required Tables for Super Admin Features

To enable Pending Registration, Authentication Logs, and Activity Logs features, you need to run the SQL script.

### Steps:

1. **Connect to your PostgreSQL database**
2. **Run the SQL script:**
   ```bash
   psql -U your_username -d your_database -f create_logs_tables.sql
   ```

   Or copy and paste the contents of `create_logs_tables.sql` into your database client (pgAdmin, DBeaver, etc.)

### What the script creates:

1. **authentication_logs table** - Logs all login attempts (successful and failed)
   - Tracks username, status, IP address, reason, and timestamp
   
2. **activity_logs table** - Logs all user activities
   - Tracks task description, user_id, and timestamp
   
3. **users.status column** - Adds status field to users table
   - Values: 'active', 'inactive', 'pending'

### After running the script:

- Authentication logs will automatically populate when users log in
- Activity logs will track user actions
- Pending registrations will show users with status='pending'
- All Super Admin pages will display real data

### Testing:

1. Log in to the system - this will create authentication and activity log entries
2. Visit Super Admin > Authentication Logs - you should see your login
3. Visit Super Admin > Activity Logs - you should see user activities
4. Create a user with status='pending' to test Pending Registration page
