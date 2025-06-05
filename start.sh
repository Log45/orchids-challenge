#!/bin/bash

# Start the backend with FastAPI (via `python app/main.py`)
cd /app/backend
python app/main.py &

# Start the frontend
cd /app/frontend
npm run dev &

# Wait for any process to exit
wait -n

# Exit with status of the first process that exits
exit $?