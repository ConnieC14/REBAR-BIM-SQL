# Use an official Python runtime as a parent image
FROM python:3.11-slim-bookworm

# Set the working directory in the container to /app
WORKDIR /app

# Add the current directory contents into the container at /app
ADD . /app

# Install UnixODBC library and any other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    curl \
    gnupg \
    unixodbc-dev \
    libgomp1 \
    libatlas-base-dev \
    libopenblas-dev \
    liblapack-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Add Microsoft repository and keys securely
RUN sh -c "curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -" \
    && apt-get update \
    && sh -c "curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list" \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && ACCEPT_EULA=Y apt-get install -y mssql-tools18

# Install any needed packages specified in requirements.txt
# RUN conda activate cbase_vim
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application code into the container
COPY . .

ENV PYTHONPATH=/app

# Set environment variables
ENV DB_SERVER=""
ENV DB_NAME=""
ENV DB_USERNAME=""
ENV DB_PASSWORD=""

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run app.py when the container launches
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]