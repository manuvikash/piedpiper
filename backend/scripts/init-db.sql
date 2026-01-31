-- Initialize databases for PiedPiper
-- Main DB is created by Docker (POSTGRES_DB=piedpiper)
-- Learning DB needs to be created separately

CREATE DATABASE piedpiper_learning;

-- Grant access
GRANT ALL PRIVILEGES ON DATABASE piedpiper_learning TO piedpiper;
