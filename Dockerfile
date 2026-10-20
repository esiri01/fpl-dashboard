# Optional: lets the app move to Cloud Run / Render later without changes.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8501
EXPOSE 8501
CMD streamlit run fpl_dashboard.py --server.port=${PORT} --server.address=0.0.0.0
