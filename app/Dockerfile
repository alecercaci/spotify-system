# Image for the Streamlit dashboard.
FROM python:3.12-slim
WORKDIR /project

# Libraries first, so a code change does not reinstall them (see loader/Dockerfile).
COPY app/requirements.txt app/requirements.txt
RUN pip install --no-cache-dir -r app/requirements.txt

COPY common/ common/
COPY app/ app/

EXPOSE 8501
# 0.0.0.0 so the page can be opened from outside the container (from the laptop's browser)
CMD ["streamlit", "run", "app/dashboard.py", "--server.address=0.0.0.0", "--server.port=8501"]
