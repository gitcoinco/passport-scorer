# Setup

## Getting Started

The Scorer API has a couple of key components to it, the API and interface being
the main two for you to set up:

```shell
.
├── api/        # Django API powering the interface and API
├── examples/   # Set of examples for working with the API
├── infra/      # Deployment infrastructure for hosting the API
├── interface/  # React-based user interface
└── test/       # End-to-end tests
```

## Setting up With Docker
A [`Docker Compose`](./docker-compose.yml) file has been provided to quickly get the API, database, verifier, celery workers, and interface
up and running. Setup instructions are provided below:

1. Download the Passport Scorer Repo

```shell
git clone https://github.com/gitcoinco/passport-scorer.git
```

2. Create a new `.env` file in the `api` directory & update the variables.

```shell
# From inside the api/ directory
cp .env-sample .env
```
Update the `DATABASE_URL` variable to `postgres://passport_scorer:passport_scorer_pwd@postgres:5432/passport_scorer`

Update the `CERAMIC_CACHE_SCORER_ID` variable to match a `SCORER_ID` you create from the scorer UI.
   (You will have to complete all these setup steps first, then you will be able to create a `SCORER_ID` from the UI & update this variable.)

3. Create a new `.env` file in the `interface` directory & update the variables.
```shell
# From inside the interface/ directory
cp .env.example .env
```
Update the `NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY` variable to an Alchemy API key you own. If you don't have one, you can create one for free [here](https://docs.alchemy.com/reference/api-overview)


4. Run and build the `Dockerfile` from the root directory. The first time you run this, it will take
   a while to build the Docker images.

```
docker-compose up --build
```
Upon subsequent runs, you can omit the `--build` flag.

5. Perform a database migration in the root directory by opening a new terminal & running:

```shell
docker-compose exec api python manage.py migrate
```

The API will be running on port 8002, interface on 3001, redis on 6379, and the database will be running on port 5432.



## Setting up Without docker

We assume that you have a working python environment set up on your machine with
the following:

- A recent version of Python
- `pipenv`

### Download this Repo

```shell
git clone https://github.com/gitcoinco/passport-scorer.git
```

### API

The following commands should be run from within the `api/` directory.

1. Create a `.env` file:

```shell
cp .env-sample .env
```

2. Activate your local virtual environment:

```
pipenv shell
```

3. Install dependencies in your virtual environment:

```
pipenv install
pipenv install --dev
```


4. Start the dev server:

```shell
gunicorn -b 127.0.0.1:8002 -w 4 -k uvicorn.workers.UvicornWorker scorer.asgi:application
```

or:

```shell
uvicorn scorer.asgi:application --reload --port 8002
```

5. Run Redis locally in a new terminal:

```shell
pipenv shell
docker run -d -p 6379:6379 redis
```

> Make sure you have Docker running

6. Start the celery worker:

```shell
celery -A scorer worker -l DEBUG  -Q score_passport_passport,score_registry_passport
```

### Migrations

You will need to run database migrations in the `api/` directory by running:

```shell
pipenv shell
python manage.py migrate
```

### Verifier

Navigate to the `verifier/` directory & run the verifier:
```shell
yarn
#yarn only needs to be run when first installing the app
yarn dev
```

### Interface

The front end is built using Next.js and is using a fairly standard installation
without much customization.

To run the front end, change into the `interface/` directory and install the
dependencies:

```
yarn
```

Copy the `.env.example` file:

```shell
cp .env.example .env
```

Update the `NEXT_PUBLIC_PASSPORT_SCORER_ALCHEMY_API_KEY` variable to an Alchemy API key you own. If you don't have one, you can create one for free [here](https://docs.alchemy.com/reference/api-overview)

To start the development server:

```
yarn dev
```

## Testing

### API

> The following assumes you are in the api/ directory and that you've already activated your local virtual environment

In the `./api` directory run (make sure your local virtual env is activated):

```
coverage run --source='.' manage.py test
```

#### pytest

> The following assumes you are in the api/ directory

We use pytest to run tests. In `./api` folder run:

```shell
pytest
```

#### bdd

> The following assumes you are in the api/ directory

- **docs**:
  - [pytest-bdd](https://pytest-bdd.readthedocs.io/en/latest/#advanced-code-generation)
  - https://automationpanda.com/2018/10/22/python-testing-101-pytest-bdd/
  - examples: https://github.com/AndyLPK247/behavior-driven-python
  - https://github.com/pytest-dev/pytest-mock
- **Location of feature file:**: ./api/account/test/features
- **cmd to generate missing code:** (run from `./api` and virtulanv): `pytest --generate-missing --feature scorer/test/features scorer/test`
  - you will need to copy & paste the code from terminal to `test_.*.py` file

### Cypress

> The following assumes you are in the test/ directory

1. Install dependencies with yarn:

```shell
yarn
```

2. Run Cypress tests:

```shell
yarn cypress run
```

3. Open Cypress:

```shell
yarn cypress open
```
