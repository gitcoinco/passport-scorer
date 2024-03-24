# https://pipenv.pypa.io/en/latest/basics/#pipenv-and-docker-containers
FROM --platform=linux/amd64 docker.io/python:3.11 AS base

RUN apt update && \
    apt install -y python3-dev libpq-dev


#########################################################
# Builder
#########################################################
FROM base AS builder

RUN pip install --user pipenv

# Tell pipenv to create venv in the current directory
ENV PIPENV_VENV_IN_PROJECT=1

ADD Pipfile.lock /usr/src/

WORKDIR /usr/src


# NOTE: If you install binary packages required for a python module, you need
# to install them again in the runtime. For example, if you need to install pycurl
# you need to have pycurl build dependencies libcurl4-gnutls-dev and libcurl3-gnutls
# In the runtime container you need only libcurl3-gnutls

# RUN apt install -y libcurl3-gnutls libcurl4-gnutls-dev
# RUN /root/.local/bin/pipenv lock

RUN /root/.local/bin/pipenv sync
RUN /usr/src/.venv/bin/python -c "import django; print(django.__version__)"


#########################################################
# Runtime
#########################################################
FROM base AS runtime

RUN mkdir -v /usr/src/venv

COPY --from=builder /usr/src/.venv/ /usr/src/.venv/
COPY . /app

RUN /usr/src/.venv/bin/python -c "import django; print(django.__version__)"
ENV PATH="/usr/src/.venv/bin/:${PATH}"

WORKDIR /app

RUN STATIC_ROOT=/app/static SECRET_KEY=secret_is_irrelevant_here CERAMIC_CACHE_SCORER_ID=1 DATABASE_URL=sqlite:////dunmmy_db.sqlite3 python manage.py collectstatic --noinput

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "scorer.asgi:application", "-b", "0.0.0.0:8000"]
