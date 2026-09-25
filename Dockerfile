FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

ARG GIT_COMMIT
ARG GIT_DIRTY

ENV EXPERIAN_GIT_COMMIT=${GIT_COMMIT}
ENV EXPERIAN_GIT_DIRTY=${GIT_DIRTY}

CMD ["uv","run","--no-sync","python","-m","experian_workflow.pipeline"]
