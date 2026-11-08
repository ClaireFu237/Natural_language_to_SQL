# Model × Effort × Question Matrix Workflow

## Core execution model

The `matrix` command runs the **full Cartesian product** of:

> **ALL models × ALL effort levels × ALL questions**

Every selected model is tested at every selected effort level, and every resulting configuration processes every question in the input file.

The total number of model/question runs is:

```text
number of models × number of effort levels × number of questions
```

For example:

```text
2 models × 3 effort levels × 20 questions = 120 model/question runs
```

This is not a one-to-one mapping between models and effort levels. Given:

```text
Models:  model-a, model-b
Efforts: low, medium, high
```

the workflow creates all six configurations:

| Model | Effort |
|---|---|
| `model-a` | `low` |
| `model-a` | `medium` |
| `model-a` | `high` |
| `model-b` | `low` |
| `model-b` | `medium` |
| `model-b` | `high` |

Each of these six configurations runs the complete question set.

## Requirements

### Local software

- Python 3.10 or newer;
- the Google Cloud CLI, including the `bq` command;
- network access to the selected LLM API and Google BigQuery;
- the Python SDK for the selected provider.

Create and activate a virtual environment:

```bash
cd "/Users/fuclaire/Desktop/holokai/Final/7.17TestBigQ copy"

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install `python-dotenv` and the SDK for the provider that will be tested:

```bash
# Gemini
python -m pip install python-dotenv google-genai

# OpenAI
python -m pip install python-dotenv openai

# Anthropic
python -m pip install python-dotenv anthropic
```

Only the SDK for the selected provider is required for a given matrix run.

### BigQuery authentication and permissions

Authenticate the Google Cloud CLI before starting the workflow:

```bash
gcloud auth login
```

Verify access to the target dataset:

```bash
bq ls --project_id=YOUR_PROJECT_ID YOUR_DATASET
```

The authenticated account normally needs:

- permission to create BigQuery query jobs, commonly provided by `BigQuery Job User` on the project;
- permission to read table metadata and data, commonly provided by `BigQuery Data Viewer` on the dataset.

### Environment configuration

Create `.env` from the supplied template if it does not already exist:

```bash
cp .env.example .env
```

Configure one LLM provider and the target BigQuery dataset. For example, a Gemini configuration requires:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash
GEMINI_THINKING_LEVEL=medium

BQ_PROJECT_ID=YOUR_PROJECT_ID
BQ_DATASET=YOUR_DATASET
BQ_LOCATION=YOUR_DATASET_LOCATION
```

Equivalent provider-specific API key and model variables are required when using OpenAI or Anthropic:

```env
# OpenAI
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_MODEL=YOUR_OPENAI_MODEL

# Anthropic
ANTHROPIC_API_KEY=YOUR_ANTHROPIC_API_KEY
ANTHROPIC_MODEL=YOUR_ANTHROPIC_MODEL
```

The following controls are strongly recommended for matrix runs:

```env
# Keep false until real query execution is intended.
BQ_AUTO_EXECUTE=false

# Reject queries whose estimated processing exceeds this number of bytes.
BQ_MAX_BYTES_BILLED=1000000000

# Maximum number of repair attempts after a failed BigQuery dry run.
BQ_MAX_REPAIR_ATTEMPTS=2

# Directory in which matrix artifacts will be saved.
WORKFLOW_DIR=workflows
```

### Question file

Prepare a non-empty JSONL, JSON, or plain-text question file. Every JSON or JSONL object must contain a non-empty `question` field. The same complete question set will be processed by every model/effort configuration.

## Example: Gemini matrix

```bash
cd "/Users/fuclaire/Desktop/holokai/Final/7.17TestBigQ copy"

python3 workflow.py matrix \
  --questions-file hard_answerable_questions.jsonl \
  --provider gemini \
  --models gemini-2.5-flash,gemini-2.5-pro \
  --efforts low,medium,high
```

Equivalent wrapper command:

```bash
./batch_matrix.sh hard_answerable_questions.jsonl \
  --provider gemini \
  --models gemini-2.5-flash,gemini-2.5-pro \
  --efforts low,medium,high
```

If the question file contains 20 questions, this example performs:

```text
2 models × 3 efforts × 20 questions = 120 initial generations
```

Additional LLM calls may occur when generated SQL fails the BigQuery dry run and the workflow attempts to repair it.

## Provider and effort support

A single matrix invocation uses one provider. Run separate matrix commands to compare providers.

| Provider | Accepted effort values |
|---|---|
| OpenAI | `none`, `minimal`, `low`, `medium`, `high`, `xhigh` |
| Anthropic | `low`, `medium`, `high`, `xhigh`, `max` |
| Gemini | `minimal`, `low`, `medium`, `high` |

An accepted workflow value is not a guarantee that every model supports it. Confirm that each selected model supports the requested effort levels.

When `--efforts` is omitted, the workflow defaults to:

- Gemini: `minimal,low,medium,high`
- OpenAI and Anthropic: `low,medium,high,xhigh`

## Question input

The `--questions-file` option accepts:

- JSONL: one object per line with a required `question` field and an optional `id` or `instance_id`;
- JSON: an array of strings or objects, or an object containing a `questions` array;
- plain text: one non-empty question per line.

Example JSONL:

```jsonl
{"id":"q1","question":"How many employees are in each department?"}
{"id":"q2","question":"Which department has the highest average salary?"}
```


## Output structure

The database schema is fetched once and reused across the complete matrix. Each model/effort configuration receives an isolated output directory:

```text
WORKFLOW_DIR/matrix-<timestamp>/
├── matrix_summary.json
├── schema.json
├── schema.md
└── runs/
    ├── <model-effort>/
    │   ├── batch_metadata.json
    │   ├── batch_summary.csv
    │   └── questions/
    │       └── <question-id>/
    │           ├── metrics.json
    │           ├── run_metadata.json
    │           ├── query.sql
    │           ├── dry_run.json
    │           └── answer.csv
    └── ...
```

`matrix_summary.json` is the top-level record of all tested configurations and their results. Each configuration also has a `batch_summary.csv` containing one row per question with status, timing, token consumption, output location, and error information.

## Important reminder

> One matrix command means **every listed model runs at every listed effort level against every question**.
>
> Always calculate `models × efforts × questions` before launching the run.
