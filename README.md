# AI Log Detective

AI Log Detective is a realistic payment service used as an investigation target for AegisAI Reliability Engine.

AegisAI will ingest this repository, analyze incidents, correlate logs with source code, identify likely root causes, and localize suspicious code.

## Investigation target

The payment service contains a database dependency:

payments-primary

A simulated database connection timeout can produce an incident that AegisAI should eventually trace to:

services/payment-api/app/database.py

and:

get_database_connection()
