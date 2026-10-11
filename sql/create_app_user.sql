-- =============================================================================
-- Optional Script: Create Dedicated App User with Least Privilege
-- Run this in MySQL Workbench as root/administrative user if you prefer
-- not to use root credentials in your .env file.
-- =============================================================================

-- 1. Create a dedicated user for the Job Search App
-- Replace 'app_secure_password_here' with a strong password of your choice.
CREATE USER IF NOT EXISTS 'job_user'@'localhost' IDENTIFIED BY 'app_secure_password_here';

-- 2. Grant standard CRUD permissions on the application database
-- (Supports both default database name 'job_recommendation_db' and 'job_search_app')
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX ON job_recommendation_db.* TO 'job_user'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX ON job_search_app.* TO 'job_user'@'localhost';

-- 3. Apply privilege changes
FLUSH PRIVILEGES;

-- 4. Verification query:
-- SHOW GRANTS FOR 'job_user'@'localhost';
