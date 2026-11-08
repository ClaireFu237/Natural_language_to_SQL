from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = ROOT / "prompts"
SUPPORTED_PROVIDERS = {"openai", "anthropic", "gemini"}
SUPPORTED_EFFORTS = {
    "openai": {"none", "minimal", "low", "medium", "high", "xhigh"},
    "anthropic": {"low", "medium", "high", "xhigh", "max"},
    "gemini": {"minimal", "low", "medium", "high"},
}
MODEL_ENV_NAMES = {
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
    "gemini": "GEMINI_MODEL",
}
EFFORT_ENV_NAMES = {
    "openai": "OPENAI_EFFORT",
    "anthropic": "ANTHROPIC_EFFORT",
    "gemini": "GEMINI_THINKING_LEVEL",
}
PRIVACY_BOUNDARY = (
    "Only schema, the user question, generated SQL, and BigQuery dry-run errors were sent "
    "to the LLM. Table rows and query results were not sent to the LLM."
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def load_environment() -> None:
    # Local settings win; unset values can fall back to the parent project's .env.
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")


def log(message: str) -> None:
    print(f"[workflow] {message}", flush=True)


def terminal_log(category: str, message: str = "") -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{category:<6}] {message}", flush=True)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_template(name: str, values: dict[str, str]) -> str:
    rendered = (PROMPTS_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


def optional_env(name: str, default: str) -> str:
    return os.getenv(name, default).strip() or default


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} in {ROOT / '.env'}, {ROOT.parent / '.env'}, or your shell.")
    return value


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def resolve_provider(value: str | None) -> str:
    provider = (value or optional_env("LLM_PROVIDER", "openai")).lower()
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise RuntimeError(f"Unsupported provider {provider!r}; use one of: {supported}.")
    return provider


def resolve_model(provider: str, value: str | None) -> str:
    env_name = MODEL_ENV_NAMES[provider]
    model = value or os.getenv(env_name, "").strip()
    if not model:
        raise RuntimeError(f"Set {env_name} or pass --model.")
    return model


def resolve_effort(provider: str, value: str | None = None) -> str | None:
    env_name = EFFORT_ENV_NAMES[provider]
    effort = (value if value is not None else os.getenv(env_name, "")).strip().lower()
    if not effort:
        return None
    if effort not in SUPPORTED_EFFORTS[provider]:
        supported = ", ".join(sorted(SUPPORTED_EFFORTS[provider]))
        raise RuntimeError(f"Unsupported {env_name} {effort!r}; use one of: {supported}.")
    return effort


def configured_output_root() -> Path:
    value = os.getenv("WORKFLOW_DIR", "workflows")
    path = Path(value)
    # Keep this test workflow's output isolated even when the parent .env says workflows.
    if not path.is_absolute():
        path = ROOT / path
    return path


def output_dir(value: str | None, prefix: str = "") -> Path:
    path = Path(value) if value else configured_output_root() / f"{prefix}{utc_stamp()}"
    if value and not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(ROOT), text=True, capture_output=True, check=False)


def command_error(result: subprocess.CompletedProcess[str]) -> str:
    parts = [part.strip() for part in (result.stderr, result.stdout) if part.strip()]
    return "\n".join(parts) or f"Command exited with status {result.returncode}."


class Metrics:
    def __init__(self, path: Path, kind: str) -> None:
        self.path = path
        self.started_perf = time.perf_counter()
        self.data: dict[str, Any] = {
            "kind": kind,
            "started_at": now_iso(),
            "finished_at": None,
            "status": "running",
            "total_time_seconds": None,
            "steps": [],
            "llm_totals": empty_tokens() | {"output_time_seconds": 0.0, "calls": 0},
        }
        self.save()

    def save(self) -> None:
        save_json(self.path, self.data)

    @contextmanager
    def step(self, name: str, **details: Any) -> Iterator[dict[str, Any]]:
        record = {
            "name": name,
            "started_at": now_iso(),
            "finished_at": None,
            "time_seconds": None,
            "status": "running",
            "token_consumption": empty_tokens(),
            **details,
        }
        self.data["steps"].append(record)
        self.save()
        started = time.perf_counter()
        try:
            yield record
        except BaseException as exc:
            record["status"] = "failed"
            record["error"] = str(exc)
            raise
        else:
            record["status"] = "completed"
        finally:
            record["finished_at"] = now_iso()
            record["time_seconds"] = round(time.perf_counter() - started, 6)
            self.save()

    def add_llm(self, record: dict[str, Any], metadata: dict[str, Any]) -> None:
        tokens = metadata["token_consumption"]
        record["llm"] = metadata
        record["token_consumption"] = tokens
        totals = self.data["llm_totals"]
        totals["calls"] += 1
        totals["output_time_seconds"] = round(
            totals["output_time_seconds"] + metadata["output_time_seconds"], 6
        )
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            if tokens[key] is None:
                totals[key] = None
            elif totals[key] is not None:
                totals[key] += tokens[key]
        self.save()

    def finish(self, status: str, error: str | None = None) -> None:
        self.data["finished_at"] = now_iso()
        self.data["status"] = status
        self.data["total_time_seconds"] = round(time.perf_counter() - self.started_perf, 6)
        if error:
            self.data["error"] = error
        self.save()


def empty_tokens() -> dict[str, int | None]:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def call_openai(prompt: str, model: str, effort: str | None = None) -> tuple[str, dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install the OpenAI SDK: pip install openai") from exc
    started = time.perf_counter()
    request: dict[str, Any] = {"model": model, "input": prompt}
    if effort is not None:
        request["reasoning"] = {"effort": effort}
    response = OpenAI().responses.create(**request)
    elapsed = round(time.perf_counter() - started, 6)
    usage = getattr(response, "usage", None)
    tokens = {
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }
    return response.output_text.strip(), {
        "provider": "openai",
        "model": model,
        "effort": effort,
        "output_time_seconds": elapsed,
        "time_definition": "API request start until the complete LLM response was received",
        "token_consumption": tokens,
    }


def call_anthropic(prompt: str, model: str, effort: str | None = None) -> tuple[str, dict[str, Any]]:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError("Install the Anthropic SDK: pip install anthropic") from exc
    started = time.perf_counter()
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": int(optional_env("ANTHROPIC_MAX_TOKENS", "4096")),
        "messages": [{"role": "user", "content": prompt}],
    }
    if effort is not None:
        request["output_config"] = {"effort": effort}
    response = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(**request)
    elapsed = round(time.perf_counter() - started, 6)
    text = "\n".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text" and getattr(block, "text", None)
    ).strip()
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", None)
    output_tokens = getattr(usage, "output_tokens", None)
    return text, {
        "provider": "anthropic",
        "model": model,
        "effort": effort,
        "output_time_seconds": elapsed,
        "time_definition": "API request start until the complete LLM response was received",
        "token_consumption": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
            if input_tokens is not None and output_tokens is not None else None,
        },
    }


def call_gemini(prompt: str, model: str, effort: str | None = None) -> tuple[str, dict[str, Any]]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Install the Google Gen AI SDK: pip install google-genai") from exc
    started = time.perf_counter()
    config = None
    if effort is not None:
        config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_level=effort)
        )
    with genai.Client(api_key=require_env("GEMINI_API_KEY")) as client:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    elapsed = round(time.perf_counter() - started, 6)
    usage = getattr(response, "usage_metadata", None)
    return (response.text or "").strip(), {
        "provider": "gemini",
        "model": model,
        "effort": effort,
        "output_time_seconds": elapsed,
        "time_definition": "API request start until the complete LLM response was received",
        "token_consumption": {
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
        },
    }


def call_model(
    prompt: str, provider: str, model: str, effort: str | None = None
) -> tuple[str, dict[str, Any]]:
    callers = {
        "openai": call_openai,
        "anthropic": call_anthropic,
        "gemini": call_gemini,
    }
    return callers[provider](prompt, model, effort)


def extract_fenced(text: str, language: str) -> str | None:
    match = re.search(rf"```{language}\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None


def parse_sql_response(text: str) -> dict[str, Any]:
    try:
        result = json.loads(extract_fenced(text, "json") or text)
    except json.JSONDecodeError:
        result = {
            "sql": (extract_fenced(text, "sql") or text).strip(),
            "confidence_level": "low",
            "confidence_score": 0.0,
            "reason": "Response was not valid JSON; SQL was extracted as a fallback.",
            "raw_response_parse_error": True,
        }
    if not isinstance(result, dict):
        raise RuntimeError("Model response JSON must be an object.")
    result.setdefault("sql", "")
    result.setdefault("confidence_level", "low")
    result.setdefault("confidence_score", 0.0)
    result.setdefault("reason", "")
    return result


def bq_base(project_id: str, location: str) -> list[str]:
    command = ["bq", "--project_id", project_id]
    if location:
        command.extend(["--location", location])
    return command


def schema_query(project_id: str, dataset: str, location: str) -> tuple[list[dict[str, str]], str]:
    max_rows = optional_env("BQ_SCHEMA_MAX_ROWS", "100000")
    if not max_rows.isdigit() or int(max_rows) <= 0:
        raise RuntimeError("BQ_SCHEMA_MAX_ROWS must be a positive integer.")
    sql = f"""SELECT table_name, column_name, data_type, is_nullable, ordinal_position
FROM `{project_id}.{dataset}.INFORMATION_SCHEMA.COLUMNS`
ORDER BY table_name, ordinal_position"""
    result = run_command(bq_base(project_id, location) + [
        "query", "--use_legacy_sql=false", "--format=json", f"--max_rows={max_rows}", sql
    ])
    if result.returncode:
        raise RuntimeError(f"BigQuery schema extraction failed:\n{command_error(result)}")
    try:
        raw_rows = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError("Could not parse BigQuery schema JSON.") from exc
    if not raw_rows:
        raise RuntimeError(f"No tables found in `{project_id}.{dataset}`.")
    if len(raw_rows) >= int(max_rows):
        raise RuntimeError(f"Schema reached BQ_SCHEMA_MAX_ROWS={max_rows}; increase the limit.")
    rows = [{
        "table_name": str(row.get("table_name", "")),
        "column_name": str(row.get("column_name", "")),
        "data_type": str(row.get("data_type", "")),
        "is_nullable": str(row.get("is_nullable", "")),
        "ordinal_position": str(row.get("ordinal_position", "")),
    } for row in raw_rows]
    lines = [f"BigQuery project: {project_id}", f"BigQuery dataset: {dataset}", "", "Tables and columns:"]
    current = None
    for row in rows:
        if row["table_name"] != current:
            current = row["table_name"]
            lines.extend(["", f"Table `{project_id}.{dataset}.{current}`"])
        nullable = "NULLABLE" if row["is_nullable"] == "YES" else "REQUIRED"
        lines.append(f"- {row['column_name']}: {row['data_type']} ({nullable})")
    return rows, "\n".join(lines).strip() + "\n"


def save_schema(directory: Path, rows: list[dict[str, str]], text: str) -> None:
    save_json(directory / "schema.json", rows)
    (directory / "schema.md").write_text(text, encoding="utf-8")


def validate_read_only(sql: str) -> None:
    normalized = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL).strip()
    statement = normalized.rstrip().rstrip(";").strip()
    if not statement:
        raise RuntimeError("Generated SQL is empty.")
    if ";" in statement:
        raise RuntimeError("Generated SQL must be a single statement.")
    if statement.split(None, 1)[0].lower() not in {"select", "with"}:
        raise RuntimeError("Generated SQL must start with SELECT or WITH.")
    blocked = re.search(
        r"\b(insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|call|execute|"
        r"declare|set|begin|commit|rollback|export\s+data|load\s+data|copy)\b",
        statement, re.IGNORECASE,
    )
    if blocked:
        raise RuntimeError(f"Refusing non-read-only SQL containing: {blocked.group(1)}")


def parse_dry_run_bytes(stdout: str, stderr: str) -> int | None:
    match = re.search(r"will process\s+([\d,]+)\s+bytes", stdout + "\n" + stderr, re.IGNORECASE)
    return int(match.group(1).replace(",", "")) if match else None


def format_bytes(value: int | None) -> str | None:
    if value is None:
        return None
    amount = float(value)
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if amount < 1000 or unit == units[-1]:
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.2f} {unit}"
        amount /= 1000
    return None


def dry_run_query(project: str, location: str, max_bytes: str, sql: str) -> dict[str, Any]:
    result = run_command(bq_base(project, location) + [
        "query", "--use_legacy_sql=false", "--dry_run",
        f"--maximum_bytes_billed={max_bytes}", sql,
    ])
    estimated = parse_dry_run_bytes(result.stdout, result.stderr)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "estimated_bytes_processed": estimated,
        "estimated_bytes_processed_human": format_bytes(estimated),
        "maximum_bytes_billed": int(max_bytes) if max_bytes.isdigit() else max_bytes,
    }


def dry_run_error(data: dict[str, Any]) -> str:
    return "\n".join(str(data.get(k, "")).strip() for k in ("stderr", "stdout") if data.get(k)) or "No output from bq."


def execute_query(
    project: str, location: str, max_bytes: str, result_max_rows: int, sql: str
) -> subprocess.CompletedProcess[str]:
    return run_command(bq_base(project, location) + [
        "query", "--use_legacy_sql=false", "--format=csv",
        f"--max_rows={result_max_rows}",
        f"--maximum_bytes_billed={max_bytes}", sql,
    ])


def csv_data_row_count(output: str) -> int:
    rows = list(csv.reader(io.StringIO(output)))
    return max(0, len(rows) - 1) if rows else 0


def config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    provider = resolve_provider(getattr(args, "provider", None))
    result_max_rows = args.result_max_rows or optional_env("BQ_RESULT_MAX_ROWS", "100000")
    if not str(result_max_rows).isdigit() or int(result_max_rows) <= 0:
        raise RuntimeError("BQ_RESULT_MAX_ROWS must be a positive integer.")
    return {
        "provider": provider,
        "model": resolve_model(provider, getattr(args, "model", None)),
        "effort": resolve_effort(provider, getattr(args, "effort", None)),
        "project_id": args.project_id or require_env("BQ_PROJECT_ID"),
        "dataset": args.dataset or require_env("BQ_DATASET"),
        "location": args.location or optional_env("BQ_LOCATION", "us-central1"),
        "max_bytes_billed": args.max_bytes_billed or optional_env("BQ_MAX_BYTES_BILLED", "1000000000"),
        "result_max_rows": int(result_max_rows),
        "max_repair_attempts": int(args.max_repair_attempts or optional_env("BQ_MAX_REPAIR_ATTEMPTS", "2")),
        "execute": args.execute or truthy(optional_env("BQ_AUTO_EXECUTE", "false")),
    }


def process_question(
    question: str,
    directory: Path,
    config: dict[str, Any],
    schema_rows: list[dict[str, str]] | None = None,
    schema_text: str | None = None,
    question_id: str | None = None,
    progress: Callable[[str, str], None] | None = None,
) -> dict[str, Any]:
    def report(category: str, message: str) -> None:
        if progress is not None:
            progress(category, message)

    directory.mkdir(parents=True, exist_ok=True)
    metrics = Metrics(directory / "metrics.json", "question")
    metadata: dict[str, Any] = {
        "created_at": now_iso(), "workflow_dir": str(directory), "question_id": question_id,
        "question": question, **config, "attempts": [], "status": "running",
        "sql_result": None, "dry_run": None, "execution": None,
        "privacy_boundary": PRIVACY_BOUNDARY,
    }
    save_json(directory / "run_metadata.json", metadata)
    try:
        if schema_rows is None or schema_text is None:
            report("SCHEMA", f"Extracting database schema '{config['dataset']}'...")
            with metrics.step("schema_extraction") as schema_step:
                schema_rows, schema_text = schema_query(
                    config["project_id"], config["dataset"], config["location"]
                )
            report("SCHEMA", f"Schema extracted in {schema_step['time_seconds']:.2f}s.")
        else:
            with metrics.step("schema_reuse", source="batch schema snapshot"):
                pass
        save_schema(directory, schema_rows, schema_text)

        report("QUESTION", question.strip())
        with metrics.step("prompt_generation"):
            prompt = render_template("sql_generation.md", {
                "project_id": config["project_id"], "dataset": config["dataset"],
                "schema": schema_text, "question": question.strip(),
            })
        attempts_dir = directory / "attempts"
        attempts_dir.mkdir(exist_ok=True)
        sql_result: dict[str, Any] | None = None
        dry_run: dict[str, Any] | None = None
        sql = ""
        total_attempts = 1 + max(0, config["max_repair_attempts"])

        for number in range(1, total_attempts + 1):
            attempt_dir = attempts_dir / f"attempt_{number:02d}"
            attempt_dir.mkdir(exist_ok=True)
            (attempt_dir / "sql_prompt.md").write_text(prompt + "\n", encoding="utf-8")
            report("LLM", f"Generating SQL (attempt {number}/{total_attempts})...")
            with metrics.step("llm_generation" if number == 1 else "llm_repair", attempt=number) as step:
                response, llm = call_model(
                    prompt, config["provider"], config["model"], config.get("effort")
                )
                metrics.add_llm(step, llm)
            (attempt_dir / "sql_response.md").write_text(response + "\n", encoding="utf-8")
            with metrics.step("response_parsing", attempt=number):
                sql_result = parse_sql_response(response)
                sql = str(sql_result["sql"]).strip()
                save_json(attempt_dir / "sql_result.json", sql_result)
            confidence = str(sql_result.get("confidence_level", "unknown")).lower()
            report(
                "LLM",
                f"Response received in {llm['output_time_seconds']:.2f}s "
                f"(confidence: {confidence}).",
            )
            attempt = {
                "attempt": number, "attempt_dir": str(attempt_dir), "llm": llm,
                "sql_result": sql_result, "dry_run": None, "status": "generated",
            }
            metadata["attempts"].append(attempt)
            save_json(directory / "run_metadata.json", metadata)
            if not sql:
                attempt["status"] = "no_sql"
                break
            report("CHECK", "Validating generated SQL as read-only...")
            with metrics.step("local_sql_validation", attempt=number):
                validate_read_only(sql)
            (attempt_dir / "query.sql").write_text(sql.rstrip(";\n") + ";\n", encoding="utf-8")
            with metrics.step("bigquery_dry_run", attempt=number):
                dry_run = dry_run_query(
                    config["project_id"], config["location"], config["max_bytes_billed"], sql
                )
            save_json(attempt_dir / "dry_run.json", dry_run)
            attempt["dry_run"] = dry_run
            if dry_run["returncode"] == 0:
                attempt["status"] = "dry_run_passed"
                break
            attempt["status"] = "dry_run_failed"
            if number < total_attempts:
                with metrics.step("repair_prompt_generation", attempt=number + 1):
                    prompt = render_template("sql_repair.md", {
                        "project_id": config["project_id"], "dataset": config["dataset"],
                        "schema": schema_text, "question": question.strip(),
                        "failed_sql": sql, "dry_run_error": dry_run_error(dry_run),
                    })

        if sql_result is None:
            raise RuntimeError("SQL generation did not produce an attempt.")
        (directory / "sql_prompt.md").write_text(prompt + "\n", encoding="utf-8")
        (directory / "sql_response.md").write_text(response + "\n", encoding="utf-8")
        save_json(directory / "sql_result.json", sql_result)
        if sql:
            (directory / "query.sql").write_text(sql.rstrip(";\n") + ";\n", encoding="utf-8")
        if dry_run is not None:
            save_json(directory / "dry_run.json", dry_run)
        metadata["sql_result"] = sql_result
        metadata["dry_run"] = dry_run
        if not sql:
            raise RuntimeError(
                f"The model did not generate SQL: {sql_result.get('reason', 'unknown reason')}"
            )
        if dry_run is None or dry_run["returncode"] != 0:
            raise RuntimeError(f"BigQuery dry run failed: {dry_run_error(dry_run or {})}")

        if config["execute"]:
            report("DB", "Executing the read-only query...")
            with metrics.step("bigquery_execution"):
                result = execute_query(
                    config["project_id"], config["location"], config["max_bytes_billed"],
                    config["result_max_rows"], sql
                )
            returned_rows = csv_data_row_count(result.stdout) if result.returncode == 0 else None
            possibly_truncated = returned_rows is not None and returned_rows >= config["result_max_rows"]
            execution = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returned_rows": returned_rows,
                "result_max_rows": config["result_max_rows"],
                "possibly_truncated": possibly_truncated,
            }
            metadata["execution"] = execution
            save_json(directory / "execution.json", execution)
            if result.returncode:
                raise RuntimeError(f"BigQuery execution failed:\n{command_error(result)}")
            if possibly_truncated:
                raise RuntimeError(
                    f"BigQuery output reached BQ_RESULT_MAX_ROWS={config['result_max_rows']} "
                    "and may be truncated; increase the limit or use paginated result retrieval."
                )
            report("SAVE", "Query succeeded; saving answer.csv...")
            (directory / "answer.csv").write_text(result.stdout.strip() + "\n", encoding="utf-8")
        metadata["status"] = "completed"
        metrics.finish("completed")
        metadata["metrics"] = metrics.data
        save_json(directory / "run_metadata.json", metadata)
        return metadata
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        metrics.finish("failed", str(exc))
        metadata["metrics"] = metrics.data
        save_json(directory / "run_metadata.json", metadata)
        return metadata


def load_questions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise RuntimeError(f"Questions file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif suffix == ".json":
        items = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(items, dict):
            items = items.get("questions", [])
    else:
        items = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not isinstance(items, list):
        raise RuntimeError("Question input must be a JSON array, JSONL records, or one question per line.")
    normalized = []
    for index, item in enumerate(items, 1):
        if isinstance(item, str):
            normalized.append({"id": f"question_{index:04d}", "question": item})
        elif isinstance(item, dict) and str(item.get("question", "")).strip():
            normalized.append({
                **item,
                "id": str(item.get("id") or item.get("instance_id") or f"question_{index:04d}"),
                "question": str(item["question"]).strip(),
            })
        else:
            raise RuntimeError(f"Question item {index} has no non-empty 'question' field.")
    if not normalized:
        raise RuntimeError("No questions found in input file.")
    return normalized


def safe_id(value: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return f"{index:04d}_{cleaned or 'question'}"


def write_batch_summary(directory: Path, results: list[dict[str, Any]]) -> None:
    fields = [
        "question_id", "question", "status", "time_seconds", "llm_output_time_seconds",
        "llm_calls", "input_tokens", "output_tokens", "total_tokens", "workflow_dir", "error",
    ]
    with (directory / "batch_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            metrics = result.get("metrics", {})
            llm = metrics.get("llm_totals", {})
            writer.writerow({
                "question_id": result.get("question_id"), "question": result.get("question"),
                "status": result.get("status"), "time_seconds": metrics.get("total_time_seconds"),
                "llm_output_time_seconds": llm.get("output_time_seconds"), "llm_calls": llm.get("calls"),
                "input_tokens": llm.get("input_tokens"), "output_tokens": llm.get("output_tokens"),
                "total_tokens": llm.get("total_tokens"), "workflow_dir": result.get("workflow_dir"),
                "error": result.get("error", ""),
            })


def answer_command(args: argparse.Namespace) -> int:
    config = config_from_args(args)
    directory = output_dir(args.workflow_dir)
    terminal_log("RUN", "Starting single-question workflow.")
    terminal_log("RUN", f"All artifacts will be saved under {directory}")
    effort = config.get("effort") or "default"
    terminal_log(
        "CONFIG",
        f"Using {config['provider']}/{config['model']}, effort={effort}.",
    )
    result = process_question(
        args.question.strip(), directory, config, progress=terminal_log
    )
    status = "success" if result["status"] == "completed" else "failed"
    elapsed = result["metrics"]["total_time_seconds"]
    terminal_log("DONE", f"Completed with status '{status}' in {elapsed:.2f}s.")
    terminal_log("DONE")
    if result["status"] == "completed":
        return 0
    print(result["error"], file=sys.stderr)
    return 1


def batch_command(args: argparse.Namespace) -> int:
    config = config_from_args(args)
    questions = load_questions(Path(args.questions_file))
    directory = output_dir(args.workflow_dir, "batch-")
    batch_metrics = Metrics(directory / "batch_metrics.json", "batch")
    metadata: dict[str, Any] = {
        "created_at": now_iso(), "batch_dir": str(directory), "questions_file": str(args.questions_file),
        "question_count": len(questions), "config": config, "status": "running", "results": [],
    }
    save_json(directory / "batch_metadata.json", metadata)
    log(f"Batch contains {len(questions)} question(s); artifacts: {directory}")
    try:
        with batch_metrics.step("shared_schema_extraction"):
            rows, schema_text = schema_query(config["project_id"], config["dataset"], config["location"])
            save_schema(directory, rows, schema_text)
        for index, item in enumerate(questions, 1):
            question_dir = directory / "questions" / safe_id(item["id"], index)
            log(f"Processing {index}/{len(questions)}: {item['id']}")
            result = process_question(
                item["question"], question_dir, config, rows, schema_text, question_id=item["id"]
            )
            result["input_record"] = item
            metadata["results"].append(result)
            save_json(directory / "batch_metadata.json", metadata)
            write_batch_summary(directory, metadata["results"])
        failed = sum(result["status"] != "completed" for result in metadata["results"])
        metadata["status"] = "completed" if failed == 0 else "completed_with_errors"
        metadata["completed_count"] = len(questions) - failed
        metadata["failed_count"] = failed
        llm_totals = batch_metrics.data["llm_totals"]
        for result in metadata["results"]:
            question_llm = result.get("metrics", {}).get("llm_totals", {})
            llm_totals["calls"] += question_llm.get("calls", 0) or 0
            llm_totals["output_time_seconds"] = round(
                llm_totals["output_time_seconds"]
                + (question_llm.get("output_time_seconds", 0) or 0),
                6,
            )
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = question_llm.get(key)
                if value is None:
                    llm_totals[key] = None
                elif llm_totals[key] is not None:
                    llm_totals[key] += value
        batch_metrics.finish(metadata["status"])
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        batch_metrics.finish("failed", str(exc))
    metadata["metrics"] = batch_metrics.data
    save_json(directory / "batch_metadata.json", metadata)
    write_batch_summary(directory, metadata["results"])
    log(f"Batch status: {metadata['status']}; total time: {batch_metrics.data['total_time_seconds']} seconds.")
    return 0 if metadata["status"] == "completed" else 1


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--location", default=None)
    parser.add_argument("--max-bytes-billed", default=None)
    parser.add_argument("--result-max-rows", default=None)
    parser.add_argument("--max-repair-attempts", default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--workflow-dir", default=None)
    parser.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument(
        "--effort",
        default=None,
        help="Override the selected provider's effort for this run.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measured BigQuery natural-language SQL workflow.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    answer = subparsers.add_parser("answer", help="Process one question")
    answer.add_argument("--question", required=True)
    add_common(answer)
    answer.set_defaults(func=answer_command)
    batch = subparsers.add_parser("batch", help="Process questions from JSONL, JSON, or text")
    batch.add_argument("--questions-file", required=True)
    add_common(batch)
    batch.set_defaults(func=batch_command)
    return parser


def main() -> None:
    load_environment()
    args = build_parser().parse_args()
    try:
        code = args.func(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
