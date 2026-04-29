FROM neurapodacr.azurecr.io/fideon-ai-ml-base:latest

WORKDIR /app

# Install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code
COPY . .

# Permissions
RUN chmod +x startup.sh setup.sh

# Create directories
RUN mkdir -p /workspace/uploads \
             /workspace/fine_tuning/training_samples \
             /workspace/fine_tuning/models \
             /workspace/logs

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["/app/startup.sh"]
