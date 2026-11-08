# BigQuery Natural-Language SQL Workflow

This project converts natural-language questions into read-only BigQuery SQL.
It supports two modes:

- **Single question**: process one question and print detailed progress logs.
- **Batch**: process questions from a JSONL, JSON, or plain-text file.

The workflow extracts the database schema, asks the selected LLM to generate
SQL, validates the SQL locally, performs a BigQuery dry run, repairs invalid
queries when possible, and optionally executes the final query.

## Requirements

- Python 3.10 or later
- Google Cloud CLI with the `bq` command installed and authenticated
- Access to the configured BigQuery project and dataset
- An API key and Python SDK for one supported LLM provider:
  - OpenAI: `pip install openai`
  - Anthropic: `pip install anthropic`
  - Gemini: `pip install google-genai`
- Optional: `pip install python-dotenv`

## Configuration

Create a local configuration file:

```bash
cp .env.example .env
```

Configure one model provider and your BigQuery connection. For example:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.6-terra
OPENAI_EFFORT=medium

BQ_PROJECT_ID=your-gcp-project
BQ_DATASET=your_dataset
BQ_LOCATION=us-central1
BQ_SCHEMA_MAX_ROWS=100000
BQ_RESULT_MAX_ROWS=100000
BQ_MAX_BYTES_BILLED=1000000000
BQ_MAX_REPAIR_ATTEMPTS=2
BQ_AUTO_EXECUTE=false

WORKFLOW_DIR=workflows
```

The workflow loads `.env` from this directory first, then uses the parent
directory's `.env` for any values that are still unset.

## Run a single question

Generate and validate SQL without executing it:

```bash
./ask.sh "How many completed orders are there?"
```

Execute the validated query and save the result as `answer.csv`:

```bash
./ask.sh --execute "How many completed orders are there?"
```

You can also call the Python entry point directly:

```bash
python3 workflow.py answer \
  --question "How many completed orders are there?" \
  --execute
```

If no question is passed to `ask.sh`, the script prompts for one interactively.

## Run a batch

```bash
./batch.sh questions.example.jsonl
./batch.sh questions.example.jsonl --execute
```

Equivalent Python commands:

```bash
python3 workflow.py batch --questions-file questions.example.jsonl
python3 workflow.py batch --questions-file questions.example.jsonl --execute
```

A failed question does not stop the remaining questions in the batch.

### Input formats

JSONL uses one object per line. The `question` field is required; `id` or
`instance_id` is optional:

```json
{"id":"q1","question":"How many completed orders are there?"}
{"id":"q2","question":"What was the total revenue last month?"}
```

JSON may contain an array of strings or objects:

```json
[
  {"id": "q1", "question": "How many completed orders are there?"},
  {"id": "q2", "question": "What was the total revenue last month?"}
]
```

It may also use a top-level `questions` property:

```json
{
  "questions": [
    "How many completed orders are there?",
    "What was the total revenue last month?"
  ]
}
```

For any other file extension, provide one non-empty question per line.

## Output files

By default, artifacts are saved under `WORKFLOW_DIR`. Relative paths are
resolved from this project directory. Use `--workflow-dir` to select a specific
output directory.

A single-question run may contain:

- `run_metadata.json`: configuration, status, attempts, and final result metadata
- `metrics.json`: end-to-end timing, step timing, and token usage
- `schema.json` and `schema.md`: extracted database schema
- `sql_prompt.md` and `sql_response.md`: final prompt and model response
- `sql_result.json`: parsed SQL and confidence information
- `query.sql`: final generated query
- `dry_run.json`: BigQuery dry-run result
- `execution.json`: query execution metadata when execution is enabled
- `answer.csv`: query result when execution succeeds
- `attempts/`: prompt, response, SQL, and dry-run artifacts for every attempt

A batch run also contains:

- `batch_metadata.json`: batch configuration, status, and per-question results
- `batch_metrics.json`: batch timing and aggregate token usage
- `batch_summary.csv`: one summary row per question
- `questions/`: complete artifacts for each question

Metrics files are written at startup and updated after every step, so failed
runs retain all measurements collected before the error.

