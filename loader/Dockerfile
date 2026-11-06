# Image for the loader, and also for the benchmark (same libraries, same code).
FROM python:3.12-slim
WORKDIR /project

# Libraries first: Docker reuses this step as long as requirements.txt does not change,
# so rebuilding after a code change takes seconds instead of reinstalling pandas.
COPY loader/requirements.txt loader/requirements.txt
RUN pip install --no-cache-dir -r loader/requirements.txt

COPY common/ common/
COPY sql/ sql/
COPY loader/ loader/
COPY measure/ measure/
ENV SQL_DIR=/project/sql

CMD ["python", "loader/load.py"]
