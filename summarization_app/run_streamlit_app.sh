#!/bin/bash

# Set environment variables to reduce Streamlit watching
export STREAMLIT_SERVER_WATCH_DIRS="false"
export STREAMLIT_SERVER_HEADLESS="true"
export STREAMLIT_SERVER_FILE_WATCHER_TYPE="none"

# Run Streamlit app
echo "Starting Streamlit app..."
python -m streamlit run app.py
