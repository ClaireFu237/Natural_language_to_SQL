from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(path: Path) -> None:
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = ROOT / "prompts"
OUTPUT_ROOT = ROOT.parent.resolve()
WORKFLOWS_DIR = OUTPUT_ROOT / "postgresql_workflows"
SUPPORTED_PROVIDERS = {"openai", "anthropic", "gemini"}
OPENAI_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
ANTHROPIC_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
GEMINI_THINKING_LEVELS = {"minimal", "low", "medium", "high"}
MODEL_ENV_NAMES = {
    "openai": "OPENAI_MODEL",
    "anthropic": "ANTHROPIC_MODEL",
    "gemini": "GEMINI_MODEL",
}
TOKEN_KEYS = (
    "input_tokens", "cached_input_tokens", "uncached_input_tokens",
    "output_tokens", "thinking_tokens", "total_tokens",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def log(message: str) -> None:
    print(f"[workflow] {message}", flush=True)


def render(name: str, values: dict[str, str]) -> str:
    text = (PROMPTS_DIR / name).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def load_environment() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT.parent / ".env")
    # Reuse the existing workflow configuration during migration without
    # copying API keys or database credentials into the new folder.
    load_dotenv(ROOT.parent / "6.25" / ".env")


def workflow_root(value: str | None) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = OUTPUT_ROOT / path
    else:
        configured = Path(os.getenv("DB_WORKSPACE", str(WORKFLOWS_DIR)))
        # Migrate legacy absolute DB_WORKSPACE values by keeping only their
        # final directory name under this repository's fixed output root.
        if configured.is_absolute() and not configured.is_relative_to(OUTPUT_ROOT):
            configured = OUTPUT_ROOT / configured.name
        elif not configured.is_absolute():
            configured = OUTPUT_ROOT / configured
        path = configured / stamp()
    path = path.resolve()
    if not path.is_relative_to(OUTPUT_ROOT):
        raise RuntimeError(
            f"Workflow output must stay inside {OUTPUT_ROOT}; got {path}. "
            "Use a relative --workflow-dir or a path under that directory."
        )
    path.mkdir(parents=True, exist_ok=True)
    return path


def provider_and_model(args: argparse.Namespace) -> tuple[str, str]:
    provider = (getattr(args, "provider", None) or os.getenv("LLM_PROVIDER") or "openai").lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise SystemExit(f"Unsupported provider: {provider}")
    env_name = MODEL_ENV_NAMES[provider]
    model = getattr(args, "model", None) or os.getenv(env_name)
    if not model:
        raise SystemExit(f"Set {env_name} or pass --model.")
    return provider, model


def provider_effort(args: argparse.Namespace, provider: str) -> str | None:
    if provider == "openai":
        value = getattr(args, "openai_reasoning_effort", None) or os.getenv("OPENAI_REASONING_EFFORT")
        supported = OPENAI_REASONING_EFFORTS
        name = "OPENAI_REASONING_EFFORT"
    elif provider == "anthropic":
        value = getattr(args, "anthropic_effort", None) or os.getenv("ANTHROPIC_EFFORT")
        supported = ANTHROPIC_EFFORTS
        name = "ANTHROPIC_EFFORT"
    else:
        value = getattr(args, "gemini_thinking_level", None) or os.getenv(
            "GEMINI_THINKING_LEVEL"
        )
        supported = GEMINI_THINKING_LEVELS
        name = "GEMINI_THINKING_LEVEL"
    if not value or not value.strip():
        return None
    effort = value.strip().lower()
    if effort not in supported:
        choices = ", ".join(sorted(supported))
        raise SystemExit(f"Unsupported {name} '{value}'. Choose one of: {choices}.")
    return effort


def empty_tokens() -> dict[str, None]:
    return {key: None for key in TOKEN_KEYS}


def openai_tokens(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return empty_tokens()
    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    inp_details = getattr(usage, "input_tokens_details", None)
    out_details = getattr(usage, "output_tokens_details", None)
    cached = getattr(inp_details, "cached_tokens", None) if inp_details else None
    return {
        "input_tokens": inp,
        "cached_input_tokens": cached,
        "uncached_input_tokens": inp - cached if inp is not None and cached is not None else None,
        "output_tokens": out,
        "thinking_tokens": getattr(out_details, "reasoning_tokens", None) if out_details else None,
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def anthropic_tokens(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return empty_tokens()
    inp = getattr(usage, "input_tokens", None)
    out = getattr(usage, "output_tokens", None)
    cached = getattr(usage, "cache_read_input_tokens", None)
    return {
        "input_tokens": inp,
        "cached_input_tokens": cached,
        "uncached_input_tokens": inp - cached if inp is not None and cached is not None else None,
        "output_tokens": out,
        "thinking_tokens": None,
        "total_tokens": inp + out if inp is not None and out is not None else None,
    }


def gemini_tokens(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return empty_tokens()
    inp = getattr(usage, "prompt_token_count", None)
    cached = getattr(usage, "cached_content_token_count", None)
    return {
        "input_tokens": inp,
        "cached_input_tokens": cached,
        "uncached_input_tokens": inp - cached
        if inp is not None and cached is not None else None,
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "thinking_tokens": getattr(usage, "thoughts_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }


def call_model(prompt: str, provider: str, model: str, effort: str | None) -> tuple[str, dict[str, Any]]:
    started_iso = now_iso()
    started = time.perf_counter()
    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the OpenAI SDK: pip install openai") from exc
        request: dict[str, Any] = {"model": model, "input": prompt}
        if effort is not None:
            request["reasoning"] = {"effort": effort}
        response = OpenAI().responses.create(**request)
        text = response.output_text.strip()
        tokens = openai_tokens(response)
    elif provider == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError("Install the Anthropic SDK: pip install anthropic") from exc
        request = {
            "model": model,
            "max_tokens": int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096")),
            "messages": [{"role": "user", "content": prompt}],
        }
        if effort is not None:
            request["output_config"] = {"effort": effort}
        response = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY")).messages.create(**request)
        text = "\n".join(
            (block.get("text") if isinstance(block, dict) else getattr(block, "text", ""))
            for block in response.content
            if (block.get("type") if isinstance(block, dict) else getattr(block, "type", None)) == "text"
        ).strip()
        tokens = anthropic_tokens(response)
    else:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Install the Google Gen AI SDK: pip install google-genai"
            ) from exc
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Set GEMINI_API_KEY in .env or your shell.")
        config = None
        if effort is not None:
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=effort)
            )
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        text = (response.text or "").strip()
        tokens = gemini_tokens(response)
    elapsed = round(time.perf_counter() - started, 6)
    return text, {
        "started_at": started_iso,
        "completed_at": now_iso(),
        "provider": provider,
        "model": model,
        "effort": effort,
        "llm_output_time_seconds": elapsed,
        "time_consumption_seconds": elapsed,
        "token_consumption": tokens,
    }


def fenced(text: str, language: str) -> str | None:
    match = re.search(rf"```{language}\s*(.*?)```", text, re.I | re.S)
    return match.group(1).strip() if match else None


def parse_result(text: str) -> dict[str, Any]:
    try:
        result = json.loads(fenced(text, "json") or text)
    except json.JSONDecodeError:
        result = {
            "sql": (fenced(text, "sql") or text).strip(),
            "confidence_level": "low", "confidence_score": 0,
            "reason": "Response was not valid JSON; extracted SQL as fallback.",
        }
    if not isinstance(result, dict) or not isinstance(result.get("sql"), str):
        raise ValueError("LLM response must be a JSON object with a string sql field.")
    result.setdefault("confidence_level", "low")
    result.setdefault("confidence_score", 0)
    result.setdefault("reason", "")
    result["sql"] = result["sql"].strip()
    return result


def validate_schema(schema: str) -> None:
    if re.search(r"\binsert\s+into\b|\bcopy\s+.+\s+from\s+stdin\b|^\s*\\\.\s*$", schema, re.I | re.M | re.S):
        raise RuntimeError("Schema appears to contain table data; refusing to send it to the LLM.")


def validate_sql(sql: str) -> None:
    normalized = re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.M | re.S).strip()
    if not normalized or normalized.split(None, 1)[0].lower() not in {"select", "with"}:
        raise RuntimeError("Generated SQL must start with SELECT or WITH.")
    blocked = re.search(r"\b(insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|copy|call|do|vacuum|analyze)\b", normalized, re.I)
    if blocked:
        raise RuntimeError(f"Refusing non-read-only SQL containing {blocked.group(1)}.")


def db_env() -> dict[str, str]:
    value = os.getenv("DB_URL") or os.getenv("VALIDATION_DATABASE_URL")
    if not value:
        raise RuntimeError("Set DB_URL (or VALIDATION_DATABASE_URL) in .env.")
    if value.startswith("DB_URL="):
        value = value.split("=", 1)[1]
    env = os.environ.copy()
    env["DB_URL"] = value
    env["DB_USERNAME"] = os.getenv("DB_USERNAME", "")
    env["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "")
    env["PGPASSWORD"] = env["DB_PASSWORD"]
    return env


def db_target_schema() -> str:
    value = os.getenv("DB_TARGET_SCHEMA", "").strip()
    if not value:
        raise RuntimeError("Set DB_TARGET_SCHEMA in .env (for example, starbucks_mock).")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", value):
        raise RuntimeError(
            "DB_TARGET_SCHEMA must be a plain PostgreSQL identifier without "
            "quotes, dots, or wildcard characters."
        )
    return value


def command(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True, check=False)


def extract_schema(path: Path, env: dict[str, str], target_schema: str) -> subprocess.CompletedProcess[str]:
    args = [
        "pg_dump",
        "--schema-only",
        "--schema", target_schema,
        "--strict-names",
        "--no-owner",
        "--no-privileges",
        "--no-password",
        "--file", str(path),
    ]
    if env.get("DB_USERNAME"):
        args += ["--username", env["DB_USERNAME"]]
    args.append(env["DB_URL"])
    return command(args, env)


class QueryError(RuntimeError):
    pass


def execute_query(sql: str, env: dict[str, str]) -> tuple[str, str]:
    validate_sql(sql)
    statement = f"BEGIN READ ONLY;\n{sql.rstrip().rstrip(';')};\nCOMMIT;"
    args = ["psql", env["DB_URL"], "--no-password", "--quiet", "--set", "ON_ERROR_STOP=1", "--pset", "footer=off", "--csv", "--command", statement]
    if env.get("DB_USERNAME"):
        args[2:2] = ["--username", env["DB_USERNAME"]]
    result = command(args, env)
    if result.returncode:
        raise QueryError(result.stderr.strip())
    return result.stdout.strip(), result.stderr.strip()


def add_step(metrics: dict[str, Any], name: str, started: float, **extra: Any) -> None:
    metrics["steps"].append({"step": name, "duration_seconds": round(time.perf_counter() - started, 6), **extra})


def token_totals(llm_steps: list[dict[str, Any]]) -> dict[str, int | None]:
    totals: dict[str, int | None] = {}
    for key in TOKEN_KEYS:
        values = [step["token_consumption"].get(key) for step in llm_steps]
        totals[key] = sum(value for value in values if isinstance(value, int)) if any(isinstance(value, int) for value in values) else None
    return totals


def finish_metrics(metrics: dict[str, Any], started: float, status: str, error: str | None = None) -> None:
    metrics["completed_at"] = now_iso()
    metrics["status"] = status
    metrics["question_processing_time_seconds"] = round(time.perf_counter() - started, 6)
    metrics["llm_output_time_seconds"] = round(sum(step["llm_output_time_seconds"] for step in metrics["llm_steps"]), 6)
    metrics["token_consumption_total"] = token_totals(metrics["llm_steps"])
    if error:
        metrics["error"] = error


def safe_name(value: str, index: int) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-.")[:80]
    return f"{index:04d}-{cleaned or 'question'}"


def question_records(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if isinstance(value, str):
                value = {"question": value}
            if not isinstance(value, dict) or not isinstance(value.get("question"), str) or not value["question"].strip():
                raise ValueError(f"Line {line_number} must contain a non-empty question field.")
            value.setdefault("instance_id", f"line-{line_number}")
            records.append(value)
    if not records:
        raise ValueError(f"No questions found in {path}.")
    return records


def prepare_schema(root: Path, env: dict[str, str], target_schema: str) -> tuple[str, dict[str, Any]]:
    directory = root / "schema_extraction"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "schema.sql"
    started = time.perf_counter()
    result = extract_schema(path, env, target_schema)
    duration = round(time.perf_counter() - started, 6)
    save_json(directory / "run.json", {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "duration_seconds": duration})
    if result.returncode:
        raise RuntimeError(f"Schema extraction failed: {result.stderr.strip()}")
    schema = path.read_text(encoding="utf-8").strip()
    validate_schema(schema)
    metadata = {
        "step": "schema_extraction",
        "duration_seconds": duration,
        "schema_path": str(path),
        "target_schema": target_schema,
    }
    save_json(directory / "result.json", metadata)
    return schema, metadata


def process_question(record: dict[str, Any], directory: Path, schema: str, target_schema: str, env: dict[str, str], provider: str, model: str, effort: str | None, max_attempts: int) -> dict[str, Any]:
    started = time.perf_counter()
    question = record["question"].strip()
    data_dir = directory / "data_extraction"
    outputs_dir = directory / "outputs"
    data_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, Any] = {"started_at": now_iso(), "question": question, "instance_id": record.get("instance_id"), "target_schema": target_schema, "steps": [], "llm_steps": []}
    metrics_path = outputs_dir / "metrics.json"
    save_json(metrics_path, metrics)
    previous_sql = error_message = None
    attempts = []
    status = "failed"
    answer_path: Path | None = None
    try:
        for attempt in range(1, max_attempts + 1):
            attempt_dir = data_dir / f"attempt_{attempt}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            step_started = time.perf_counter()
            prompt = render(
                "query_generation.md",
                {"schema": schema, "question": question, "target_schema": target_schema},
            )
            if previous_sql and error_message:
                prompt += "\n\n" + render("query_retry.md", {"previous_sql": previous_sql, "error_message": error_message})
            (attempt_dir / "prompt.md").write_text(prompt + "\n", encoding="utf-8")
            response, llm = call_model(prompt, provider, model, effort)
            llm_step = {"step": "query_generation", "attempt": attempt, **llm}
            metrics["llm_steps"].append(llm_step)
            add_step(metrics, "llm_query_generation", step_started, attempt=attempt, llm_output_time_seconds=llm["llm_output_time_seconds"], token_consumption=llm["token_consumption"])
            (attempt_dir / "response.md").write_text(response + "\n", encoding="utf-8")
            result = parse_result(response)
            save_json(attempt_dir / "result.json", result)
            # Keep the same convenient top-level "latest attempt" artifacts as
            # the original workflow while retaining every attempt separately.
            (data_dir / "prompt.md").write_text(prompt + "\n", encoding="utf-8")
            (data_dir / "response.md").write_text(response + "\n", encoding="utf-8")
            save_json(data_dir / "result.json", result)
            save_json(metrics_path, metrics)
            if result.get("confidence_level") == "cannot_answer":
                answer_path = outputs_dir / "answer.json"
                save_json(answer_path, {"status": "cannot_answer", "reason": result.get("reason"), "question": question})
                attempts.append({"attempt": attempt, "status": "cannot_answer", "reason": result.get("reason"), "llm": llm})
                status = "cannot_answer"
                break
            sql = result["sql"]
            validate_sql(sql)
            query_path = attempt_dir / "query.sql"
            query_path.write_text(sql.rstrip().rstrip(";") + ";\n", encoding="utf-8")
            (data_dir / "query.sql").write_text(sql.rstrip().rstrip(";") + ";\n", encoding="utf-8")
            sql_started = time.perf_counter()
            try:
                answer, stderr = execute_query(sql, env)
                add_step(metrics, "sql_execution", sql_started, attempt=attempt, status="success")
                answer_path = outputs_dir / "answer.csv"
                answer_path.write_text(answer + "\n", encoding="utf-8")
                attempts.append({"attempt": attempt, "status": "success", "stderr": stderr, "query_path": str(query_path)})
                status = "success"
                break
            except QueryError as exc:
                add_step(metrics, "sql_execution", sql_started, attempt=attempt, status="failed", error=str(exc))
                attempts.append({"attempt": attempt, "status": "failed", "error": str(exc), "query_path": str(query_path)})
                previous_sql, error_message = sql, str(exc)
                save_json(metrics_path, metrics)
                if attempt == max_attempts:
                    raise RuntimeError(f"Query execution failed after {max_attempts} attempts: {exc}") from exc
        finish_metrics(metrics, started, status)
        metadata = {"status": status, "question_record": record, "answer_path": str(answer_path) if answer_path else None, "attempts": attempts, "metrics": metrics}
        save_json(outputs_dir / "run_metadata.json", metadata)
        save_json(data_dir / "run.json", {"status": status, "attempts": attempts})
        save_json(metrics_path, metrics)
        return metadata
    except Exception as exc:
        finish_metrics(metrics, started, "failed", str(exc))
        save_json(metrics_path, metrics)
        save_json(outputs_dir / "run_metadata.json", {"status": "failed", "question_record": record, "attempts": attempts, "metrics": metrics, "error": str(exc)})
        raise


def answer(args: argparse.Namespace) -> None:
    load_environment()
    provider, model = provider_and_model(args)
    effort = provider_effort(args, provider)
    target_schema = db_target_schema()
    root = workflow_root(args.workflow_dir)
    env = db_env()
    run_started = time.perf_counter()
    run_started_at = now_iso()
    schema, schema_metric = prepare_schema(root, env, target_schema)
    record = {"instance_id": "single", "question": args.question}
    result = process_question(record, root, schema, target_schema, env, provider, model, effort, args.max_attempts)
    summary = {"mode": "single", "started_at": run_started_at, "completed_at": now_iso(), "run_time_seconds": round(time.perf_counter() - run_started, 6), "provider": provider, "model": model, "effort": effort, "schema_extraction": schema_metric, "result": result}
    save_json(root / "run_summary.json", summary)
    log(f"Completed with status {result['status']}; saved under {root}")


def batch_answer(args: argparse.Namespace) -> None:
    load_environment()
    provider, model = provider_and_model(args)
    effort = provider_effort(args, provider)
    target_schema = db_target_schema()
    source = Path(args.questions).resolve()
    records = question_records(source)
    root = workflow_root(args.workflow_dir)
    env = db_env()
    run_started = time.perf_counter()
    schema, schema_metric = prepare_schema(root, env, target_schema)
    summary: dict[str, Any] = {"mode": "batch", "started_at": now_iso(), "source": str(source), "provider": provider, "model": model, "effort": effort, "schema_extraction": schema_metric, "question_count": len(records), "results": []}
    summary_path = root / "batch_summary.json"
    save_json(summary_path, summary)
    for index, record in enumerate(records, 1):
        identifier = str(record.get("instance_id", f"question-{index}"))
        directory = root / "questions" / safe_name(identifier, index)
        log(f"Processing question {index}/{len(records)} ({identifier})")
        try:
            result = process_question(record, directory, schema, target_schema, env, provider, model, effort, args.max_attempts)
            item = {"index": index, "instance_id": identifier, "status": result["status"], "question_dir": str(directory), "question_processing_time_seconds": result["metrics"]["question_processing_time_seconds"], "llm_output_time_seconds": result["metrics"]["llm_output_time_seconds"], "token_consumption_total": result["metrics"]["token_consumption_total"]}
        except Exception as exc:
            metrics = json.loads((directory / "outputs" / "metrics.json").read_text(encoding="utf-8"))
            item = {"index": index, "instance_id": identifier, "status": "failed", "error": str(exc), "question_dir": str(directory), "question_processing_time_seconds": metrics.get("question_processing_time_seconds"), "llm_output_time_seconds": metrics.get("llm_output_time_seconds"), "token_consumption_total": metrics.get("token_consumption_total")}
            if not args.continue_on_error:
                summary["results"].append(item)
                save_json(summary_path, summary)
                raise
        summary["results"].append(item)
        save_json(summary_path, summary)
    summary["completed_at"] = now_iso()
    summary["run_time_seconds"] = round(time.perf_counter() - run_started, 6)
    summary["counts"] = {status: sum(item["status"] == status for item in summary["results"]) for status in ("success", "cannot_answer", "failed")}
    save_json(summary_path, summary)
    log(f"Batch completed; summary saved to {summary_path}")


def comma_values(value: str | None, option: str) -> list[str]:
    values = [item.strip() for item in (value or "").split(",") if item.strip()]
    if not values:
        raise RuntimeError(f"{option} must contain at least one value.")
    return list(dict.fromkeys(values))


def matrix_answer(args: argparse.Namespace) -> None:
    load_environment()
    requested_models = comma_values(args.models, "--models") if args.models else None
    if requested_models and not getattr(args, "model", None):
        args.model = requested_models[0]
    provider, default_model = provider_and_model(args)
    models = requested_models or [default_model]
    default_efforts = (
        "minimal,low,medium,high"
        if provider == "gemini"
        else "low,medium,high,xhigh"
    )
    efforts = comma_values(args.efforts or default_efforts, "--efforts")
    for effort in efforts:
        effort_args = argparse.Namespace(
            openai_reasoning_effort=effort if provider == "openai" else None,
            anthropic_effort=effort if provider == "anthropic" else None,
            gemini_thinking_level=effort if provider == "gemini" else None,
        )
        provider_effort(effort_args, provider)

    target_schema = db_target_schema()
    source = Path(args.questions).resolve()
    records = question_records(source)
    root = workflow_root(args.workflow_dir)
    env = db_env()
    started = time.perf_counter()
    schema, schema_metric = prepare_schema(root, env, target_schema)
    summary: dict[str, Any] = {
        "mode": "matrix",
        "started_at": now_iso(),
        "source": str(source),
        "provider": provider,
        "models": models,
        "efforts": efforts,
        "configuration_count": len(models) * len(efforts),
        "question_count": len(records),
        "schema_extraction": schema_metric,
        "status": "running",
        "runs": [],
    }
    summary_path = root / "matrix_summary.json"
    save_json(summary_path, summary)
    log(
        f"Matrix contains {len(models)} model(s) x {len(efforts)} effort(s) "
        f"x {len(records)} question(s); artifacts: {root}"
    )

    for model in models:
        for effort in efforts:
            run_dir = root / "runs" / safe_name(
                f"{model}-{effort}", len(summary["runs"]) + 1
            )
            run: dict[str, Any] = {
                "provider": provider,
                "model": model,
                "effort": effort,
                "run_dir": str(run_dir),
                "status": "running",
                "results": [],
            }
            summary["runs"].append(run)
            save_json(summary_path, summary)
            log(f"Starting model={model}, effort={effort}")
            for index, record in enumerate(records, 1):
                identifier = str(record.get("instance_id", f"question-{index}"))
                directory = run_dir / "questions" / safe_name(identifier, index)
                log(
                    f"[{model}/{effort}] Processing "
                    f"{index}/{len(records)} ({identifier})"
                )
                try:
                    result = process_question(
                        record,
                        directory,
                        schema,
                        target_schema,
                        env,
                        provider,
                        model,
                        effort,
                        args.max_attempts,
                    )
                    item = {
                        "index": index,
                        "instance_id": identifier,
                        "status": result["status"],
                        "question_dir": str(directory),
                        "question_processing_time_seconds":
                            result["metrics"]["question_processing_time_seconds"],
                        "llm_output_time_seconds":
                            result["metrics"]["llm_output_time_seconds"],
                        "token_consumption_total":
                            result["metrics"]["token_consumption_total"],
                    }
                except Exception as exc:
                    metrics_path = directory / "outputs" / "metrics.json"
                    metrics = (
                        json.loads(metrics_path.read_text(encoding="utf-8"))
                        if metrics_path.exists()
                        else {}
                    )
                    item = {
                        "index": index,
                        "instance_id": identifier,
                        "status": "failed",
                        "error": str(exc),
                        "question_dir": str(directory),
                        "question_processing_time_seconds":
                            metrics.get("question_processing_time_seconds"),
                        "llm_output_time_seconds":
                            metrics.get("llm_output_time_seconds"),
                        "token_consumption_total":
                            metrics.get("token_consumption_total"),
                    }
                    if not args.continue_on_error:
                        run["results"].append(item)
                        run["status"] = "failed"
                        save_json(run_dir / "batch_summary.json", run)
                        save_json(summary_path, summary)
                        raise
                run["results"].append(item)
                save_json(run_dir / "batch_summary.json", run)
                save_json(summary_path, summary)
            run["counts"] = {
                status: sum(item["status"] == status for item in run["results"])
                for status in ("success", "cannot_answer", "failed")
            }
            run["status"] = (
                "completed" if run["counts"]["failed"] == 0 else "completed_with_errors"
            )
            save_json(run_dir / "batch_summary.json", run)
            save_json(summary_path, summary)

    failed_runs = sum(run["status"] != "completed" for run in summary["runs"])
    summary["status"] = "completed" if failed_runs == 0 else "completed_with_errors"
    summary["completed_at"] = now_iso()
    summary["run_time_seconds"] = round(time.perf_counter() - started, 6)
    summary["completed_run_count"] = len(summary["runs"]) - failed_runs
    summary["failed_run_count"] = failed_runs
    save_json(summary_path, summary)
    log(f"Matrix completed with status {summary['status']}; summary saved to {summary_path}")


def generate_query(args: argparse.Namespace) -> None:
    load_environment()
    provider, model = provider_and_model(args)
    effort = provider_effort(args, provider)
    target_schema = db_target_schema()
    root = workflow_root(args.workflow_dir)
    schema = Path(args.schema).resolve().read_text(encoding="utf-8").strip()
    validate_schema(schema)
    record = {"instance_id": args.instance_id or "single", "question": args.question}
    directory = root / "data_extraction"
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    prompt = render(
        "query_generation.md",
        {"schema": schema, "question": args.question.strip(), "target_schema": target_schema},
    )
    (directory / "prompt.md").write_text(prompt + "\n", encoding="utf-8")
    response, llm = call_model(prompt, provider, model, effort)
    result = parse_result(response)
    if result.get("confidence_level") != "cannot_answer":
        validate_sql(result["sql"])
    (directory / "response.md").write_text(response + "\n", encoding="utf-8")
    (directory / "query.sql").write_text(result["sql"].rstrip().rstrip(";") + (";\n" if result["sql"] else ""), encoding="utf-8")
    metrics = {"question": record["question"], "question_processing_time_seconds": round(time.perf_counter() - started, 6), "llm_output_time_seconds": llm["llm_output_time_seconds"], "steps": [{"step": "query_generation", **llm}], "token_consumption_total": llm["token_consumption"]}
    save_json(directory / "result.json", {"result": result, "metrics": metrics})
    log(f"SQL and metrics saved under {directory}")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Postgres schema -> LLM SQL -> local read-only query workflow")
    result.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=None)
    result.add_argument("--model", default=None)
    result.add_argument("--openai-reasoning-effort", choices=sorted(OPENAI_REASONING_EFFORTS), default=None)
    result.add_argument("--anthropic-effort", choices=sorted(ANTHROPIC_EFFORTS), default=None)
    result.add_argument("--gemini-thinking-level", choices=sorted(GEMINI_THINKING_LEVELS), default=None)
    subs = result.add_subparsers(dest="command", required=True)
    one = subs.add_parser("answer", help="Process one question")
    one.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=argparse.SUPPRESS)
    one.add_argument("--model", default=argparse.SUPPRESS)
    one.add_argument("--openai-reasoning-effort", choices=sorted(OPENAI_REASONING_EFFORTS), default=argparse.SUPPRESS)
    one.add_argument("--anthropic-effort", choices=sorted(ANTHROPIC_EFFORTS), default=argparse.SUPPRESS)
    one.add_argument("--gemini-thinking-level", choices=sorted(GEMINI_THINKING_LEVELS), default=argparse.SUPPRESS)
    one.add_argument("--question", required=True)
    one.add_argument("--workflow-dir")
    one.add_argument("--max-attempts", type=int, default=3)
    one.set_defaults(func=answer)
    batch = subs.add_parser("batch-answer", help="Process every question in a JSONL file")
    batch.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=argparse.SUPPRESS)
    batch.add_argument("--model", default=argparse.SUPPRESS)
    batch.add_argument("--openai-reasoning-effort", choices=sorted(OPENAI_REASONING_EFFORTS), default=argparse.SUPPRESS)
    batch.add_argument("--anthropic-effort", choices=sorted(ANTHROPIC_EFFORTS), default=argparse.SUPPRESS)
    batch.add_argument("--gemini-thinking-level", choices=sorted(GEMINI_THINKING_LEVELS), default=argparse.SUPPRESS)
    batch.add_argument("--questions", required=True)
    batch.add_argument("--workflow-dir")
    batch.add_argument("--max-attempts", type=int, default=3)
    batch.add_argument("--continue-on-error", action=argparse.BooleanOptionalAction, default=True)
    batch.set_defaults(func=batch_answer)
    matrix = subs.add_parser(
        "matrix",
        help="Run every question for every model x effort combination",
    )
    matrix.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=argparse.SUPPRESS)
    matrix.add_argument("--model", default=argparse.SUPPRESS)
    matrix.add_argument("--questions", required=True)
    matrix.add_argument(
        "--models",
        help="Comma-separated model IDs. Defaults to --model or the provider's model env var.",
    )
    matrix.add_argument(
        "--efforts",
        default=None,
        help=(
            "Comma-separated effort levels (default: minimal,low,medium,high for "
            "Gemini; low,medium,high,xhigh otherwise)."
        ),
    )
    matrix.add_argument("--workflow-dir")
    matrix.add_argument("--max-attempts", type=int, default=3)
    matrix.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    matrix.set_defaults(func=matrix_answer)
    query = subs.add_parser("generate-query", help="Generate SQL without executing it")
    query.add_argument("--provider", choices=sorted(SUPPORTED_PROVIDERS), default=argparse.SUPPRESS)
    query.add_argument("--model", default=argparse.SUPPRESS)
    query.add_argument("--openai-reasoning-effort", choices=sorted(OPENAI_REASONING_EFFORTS), default=argparse.SUPPRESS)
    query.add_argument("--anthropic-effort", choices=sorted(ANTHROPIC_EFFORTS), default=argparse.SUPPRESS)
    query.add_argument("--gemini-thinking-level", choices=sorted(GEMINI_THINKING_LEVELS), default=argparse.SUPPRESS)
    query.add_argument("--schema", required=True)
    query.add_argument("--question", required=True)
    query.add_argument("--instance-id")
    query.add_argument("--workflow-dir")
    query.set_defaults(func=generate_query)
    return result


def main() -> None:
    args = parser().parse_args()
    if hasattr(args, "max_attempts") and args.max_attempts < 1:
        raise SystemExit("--max-attempts must be at least 1")
    try:
        args.func(args)
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
