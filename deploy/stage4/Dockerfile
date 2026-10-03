ARG PYTHON_IMAGE
ARG UV_IMAGE
FROM ${UV_IMAGE} AS uv
FROM ${PYTHON_IMAGE} AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_PROGRESS=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /build
COPY pyproject.toml uv.lock ./
COPY vendor/qualified/scaffoldctl ./vendor/qualified/scaffoldctl
COPY vendor/qualified/truth-serum ./vendor/qualified/truth-serum
COPY src ./src
RUN uv lock --check && uv sync --locked --no-dev --no-editable --no-cache
FROM ${PYTHON_IMAGE} AS runtime
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/CollaborativeMinD/hmt-edge-robot-" \
      org.opencontainers.image.revision=${SOURCE_COMMIT}
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    TMPDIR=/run/hmt-scratch OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
COPY --from=builder /opt/venv /opt/venv
RUN mkdir -p /data /run/hmt-scratch && chown 10001:10001 /data /run/hmt-scratch
USER 10001:10001
WORKDIR /data
CMD ["hmt-edge-robot", "serve", "--database", "/data/cell.db", "--policy", "/etc/hmt/runtime-policy.json"]
