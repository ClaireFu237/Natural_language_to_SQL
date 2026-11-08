## Requirements

- Python 3.10 or later
- PostgreSQL command-line tools: `pg_dump` and `psql`
- Access to a PostgreSQL database
- An OpenAI or Anthropic API key

Install the Python package for the provider you plan to use:

```bash
python3 -m pip install openai python-dotenv
```

For Anthropic:

```bash
python3 -m pip install anthropic python-dotenv
```

Verify that the PostgreSQL tools are available:

```bash
pg_dump --version
psql --version
```

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit `.env` and replace the placeholder values. A minimal OpenAI configuration looks like this:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=your_openai_model
OPENAI_REASONING_EFFORT=medium

DB_URL=postgresql://localhost:5432/postgres
DB_USERNAME=postgres
DB_PASSWORD=your_database_password
DB_TARGET_SCHEMA=your_schema_name
DB_WORKSPACE=DemoResult
```

To use Anthropic instead, configure:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key
ANTHROPIC_MODEL=your_anthropic_model
ANTHROPIC_EFFORT=medium
ANTHROPIC_MAX_TOKENS=4096
```
## Answer One Question

The simplest command is:

```bash
./ask.sh "How many completed orders are there?"
```

If no question is supplied, `ask.sh` prompts for one interactively:

```bash
./ask.sh
```

You can also run the Python command directly:

```bash
python3 workflow.py answer --question "How many completed orders are there?"
```

Useful options include:

```bash
python3 workflow.py answer \
  --question "How many completed orders are there?" \
  --max-attempts 3 \
  --workflow-dir DemoResult/my-run
```

## Answer Questions in Batch

Create a JSONL file with one JSON object per line. Each object must contain a non-empty `question`. A unique `instance_id` is recommended:

```json
{"instance_id":"q-001","question":"How many completed orders are there?"}
{"instance_id":"q-002","question":"Who are the top 10 customers?"}
```

Run a batch file:

```bash
./ask_batch.sh hard_answerable_questions.jsonl
```

Or run the Python command directly:

```bash
python3 workflow.py batch-answer --questions hard_answerable_questions.jsonl
```

By default, a failed question does not stop the rest of the batch. To stop on the first error:

```bash
python3 workflow.py batch-answer \
  --questions hard_answerable_questions.jsonl \
  --no-continue-on-error
```

## Override the Provider or Model

Command-line options override values loaded from `.env` for the current run:

```bash
python3 workflow.py answer \
  --provider openai \
  --model your_openai_model \
  --openai-reasoning-effort high \
  --question "How many completed orders are there?"
```

```bash
python3 workflow.py batch-answer \
  --provider anthropic \
  --model your_anthropic_model \
  --anthropic-effort medium \
  --questions hard_answerable_questions.jsonl
```

## Generate SQL Without Executing It

If you already have a schema file and only want to generate SQL, use `generate-query`:

```bash
python3 workflow.py generate-query \
  --schema path/to/schema.sql \
  --question "How many completed orders are there?"
```

This mode still requires `DB_TARGET_SCHEMA` because the schema restriction is included in the model prompt.


## Troubleshooting

Show all available commands:

```bash
python3 workflow.py --help
```

Show options for a specific command:

```bash
python3 workflow.py answer --help
python3 workflow.py batch-answer --help
```

Common errors:

- `Set DB_TARGET_SCHEMA`: add a valid PostgreSQL schema name to `.env`.
- `Set DB_URL`: add the PostgreSQL connection URL to `.env`.
- `Set OPENAI_MODEL` or `Set ANTHROPIC_MODEL`: configure a model for the selected provider or pass `--model`.
- `pg_dump: command not found` or `psql: command not found`: install the PostgreSQL client tools and add them to `PATH`.
- Provider SDK import errors: install `openai` or `anthropic` with `python3 -m pip`.
- Schema extraction errors: verify the database URL, credentials, target schema, network access, and PostgreSQL client/server compatibility.
