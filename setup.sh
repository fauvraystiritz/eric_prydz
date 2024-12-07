#!/bin/bash

# Install dependencies using Rye
rye sync

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "DB_NAME=your_db_name
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost" > .env
    echo "Created .env file - please update with your actual credentials"
fi

echo "Setup complete! Use 'rye shell' to activate the virtual environment"