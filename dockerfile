FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the Streamlit port
EXPOSE 8501

# Run the Streamlit web server by default
CMD ["python", "-m", "streamlit", "run", "commute_tool_streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]