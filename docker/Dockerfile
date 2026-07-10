FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir agentos

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
