# Generate test data

## generate the file `test_data/generated_accounts_100.json`

- `cd ./test_data`
- make sure you have the pipenv environment create: `pipenv install`
- enter the pipenv: `pipenv shell`
- create the `.env` file, and configure the mnemonic (see the `.env-example`)
  - tip: stick to the default values where these are specified in `.env-example`
- adjust the `generate_test_accounts.py`
- run `python generate_test_accounts.py`

## generate the file `test_data/vcs/*`

- make sure you create the folder `test_data/vcs`
- run `python generate_test_vcs.py`
- the results will be written to individual files in the `test_data/vcs` folder

## generate `generate_test_auth_tokens/user-tokens.json`

- `cd generate_test_auth_tokens`
- run `npm install`
- make sure to set the environment variables:

```bash
export MNEMONIC='chief loud snack trend chief net field husband vote message decide replace'
export ALCHEMY_API_KEY='<YOUR API KEY>'
```

- run `node script_backup.js`
- the output will be written to `generate_test_auth_tokens/user-tokens.json`

Adjust the `script.js`:

- make sure to set a valid scorer id: `const scorerId = 24;`
- make sure to set a valid api key: `const apiKey = "...";`
- make sure you remove the API limit for the API key

# Running

## Locally

Run locally like:
`k6 run -e SCORER_API_KEY=<your API key> -e SCORER_ID=<your scorer id> --vus 10 --duration 30s test_scripts/scorer_api_script.js`
or
`k6 run -e SCORER_API_KEY=<your API key> -e SCORER_ID=<your scorer id> test_scripts/scorer_api_script.js`

To output results / stats in a CSV file, run k6 with the `--out` like:
`k6 run -e SCORER_API_KEY='iE7QwgX9.rx9XIXdkPwZUYAHditFMgFVKvDp428OH' -e SCORER_ID=24 --vus 10 --duration 120s --out csv=k6_metrics.csv test_scripts/scorer_api_script.js`

You can then use the `stats.ipynb` to analyse the results from the `k6_metrics.csv` (after the run).

## In cloud

First make sure to set the environment variables:
https://k6.io/docs/cloud/manage/environment-variables/

Then run in cloud like:
`k6 cloud --vus 1000 --duration 30m script.js`

# IAM Tests

The IAM tests require you to run an additional local server in order to sign
challenge messages.

This means that the tests can't be run in the cloud, unless you host this script
somewhere.

Run the local server like `node test_data/iam_signer_server.js`, then run the
tests with:

`k6 run --vus 1000 --duration 15m --out csv=k6_metrics.csv test_scripts/iam_script.js`
