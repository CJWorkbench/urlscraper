FROM workbenchdata/arrow-tools:v1.0.0 AS arrow-tools
FROM workbenchdata/parquet-to-arrow:v2.1.0 AS parquet-to-arrow


FROM python:3.8.7-buster

COPY --from=arrow-tools /usr/bin/csv-to-arrow /usr/bin/
COPY --from=parquet-to-arrow /usr/bin/parquet-to-arrow /usr/bin/

RUN true \
    && mkdir /src \
    && touch /src/README.md \
    && python -mpip install tox

COPY poetry.lock pyproject.toml /src/
WORKDIR /src
# Install everything ... even though tests will fail
RUN tox || true

COPY README.md urlscraper.py /src/
COPY tests/ /src/tests/

RUN tox
