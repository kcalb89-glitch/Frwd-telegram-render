#!/bin/bash
# Setup script for Render deployment

# Copy requirements file to the standard name
cp requirements.txt.render requirements.txt

# Create empty config.json if it doesn't exist
if [ ! -f config.json ]; then
    echo '{}' > config.json
    echo "Created empty config.json file"
fi

# Create necessary directories
mkdir -p tmp
mkdir -p logs

# Make sure replacement image exists
if [ ! -f replacement_image.png ]; then
    echo "Warning: replacement_image.png not found. Please add it to your repository."
fi

echo "Setup for Render deployment complete!"
echo "Remember to set the following environment variables in your Render dashboard:"
echo "- API_ID"
echo "- API_HASH"
echo "- SOURCE_CHANNEL"
echo "- DESTINATION_CHANNEL"
echo "- SESSION_STRING (optional)"
echo "- TEXT_FILTERS (optional)"