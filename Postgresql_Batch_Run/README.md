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

- Python 3.10 or newer;
- PostgreSQL command-line tools: `pg_dump` and `psql`;
- a PostgreSQL account that can read the configured target schema;
- an API key and Python SDK for the selected LLM provider.

Install the SDK for the provider you plan to use:

```bash
python3 -m pip install python-dotenv openai
# or
python3 -m pip install python-dotenv anthropic
# or
python3 -m pip install python-dotenv google-genai
```

Configure `.env` with the PostgreSQL connection, target schema, provider, model, and API key. For example:

```dotenv
DB_URL=postgresql://localhost:5432/postgres
DB_USERNAME=postgres
DB_PASSWORD=replace-with-your-password
DB_TARGET_SCHEMA=your_schema

LLM_PROVIDER=gemini
GEMINI_API_KEY=replace-with-your-api-key
GEMINI_MODEL=your-gemini-model
GEMINI_THINKING_LEVEL=medium
```

Use `OPENAI_API_KEY` and `OPENAI_MODEL` for OpenAI, or `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` for Anthropic. Do not commit real credentials.

## Example: Gemini matrix

```bash
cd "/Users/fuclaire/Desktop/holokai/Final/7.17TestPostgreSQL copy"

python3 workflow.py matrix \
  --questions hard_answerable_questions.jsonl \
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

Additional LLM calls may occur when generated SQL fails during PostgreSQL execution and the workflow attempts to repair it. Each query is validated as read-only and executed with `psql` inside a `BEGIN READ ONLY` transaction.

## Provider and effort support

A single matrix invocation uses one provider. Run separate matrix commands to compare providers.

| Provider | Accepted effort values |
|---|---|
| OpenAI | `none`, `low`, `medium`, `high`, `xhigh`, `max` |
| Anthropic | `low`, `medium`, `high`, `xhigh`, `max` |
| Gemini | `minimal`, `low`, `medium`, `high` |

An accepted workflow value is not a guarantee that every model supports it. Confirm that each selected model supports the requested effort levels.

When `--efforts` is omitted, the workflow defaults to:

- Gemini: `minimal,low,medium,high`
- OpenAI and Anthropic: `low,medium,high,xhigh`

## Question input

The `--questions` option accepts a JSONL file. Each non-empty line must be either:

- an object with a required `question` field and an optional `instance_id`; or
- a JSON string containing the question.

Example JSONL:

```jsonl
{"instance_id":"q1","question":"How many employees are in each department?"}
{"instance_id":"q2","question":"Which department has the highest average salary?"}
```

## Output structure

The PostgreSQL schema is extracted once with `pg_dump --schema-only` and reused across the complete matrix. Each model/effort configuration receives an isolated output directory:

```text
WORKFLOW_DIR/<timestamp>/
├── matrix_summary.json
├── schema_extraction/
│   ├── schema.sql
│   ├── run.json
│   └── result.json
└── runs/
    ├── <model-effort>/
    │   ├── batch_summary.json
    │   └── questions/
    │       └── <question-id>/
    │           ├── data_extraction/
    │           │   ├── prompt.md
    │           │   ├── response.md
    │           │   ├── result.json
    │           │   ├── query.sql
    │           │   ├── run.json
    │           │   └── attempt_<n>/
    │           └── outputs/
    │               ├── metrics.json
    │               ├── run_metadata.json
    │               └── answer.csv
    └── ...
```

If the model determines that the schema cannot answer a question, the workflow writes `answer.json` instead of `answer.csv`.

`matrix_summary.json` is the top-level record of all tested configurations and their results. Each configuration also has a `batch_summary.json` containing one result per question with status, timing, token consumption, output location, and error information.

By default, `WORKFLOW_DIR` is the `postgresql_workflows` directory beside this project folder. It can be changed with `DB_WORKSPACE` or `--workflow-dir`, but the resolved output must remain under the project's parent directory.

## Important reminder

> One matrix command means **every listed model runs at every listed effort level against every question**.
>
> Always calculate `models × efforts × questions` before launching the run.
