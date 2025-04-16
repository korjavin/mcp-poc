# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Credentials will be loaded from environment variables, no file copy needed.

# Copy the rest of the application code into the container at /app
COPY . .

# Make port 8080 available to the world outside this container (if needed for OAuth callback)
# Adjust port if necessary
EXPOSE 8080

# Define environment variable (optional, can be set in docker-compose)
# ENV NAME World

# Run main.py when the container launches
# Assuming your main bot script will be named main.py
CMD ["python", "main.py"]