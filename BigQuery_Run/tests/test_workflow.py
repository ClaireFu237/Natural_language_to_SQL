import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import workflow


class WorkflowTests(unittest.TestCase):
    def config(self):
        return {
            "provider": "openai",
            "model": "test-model",
            "project_id": "project",
            "dataset": "dataset",
            "location": "US",
            "max_bytes_billed": "1000",
            "result_max_rows": 100000,
            "max_repair_attempts": 1,
            "execute": False,
        }

    def test_question_saves_per_attempt_metrics_and_totals(self):
        responses = [
            ('{"sql":"SELECT missing","confidence_level":"low","confidence_score":0.2,"reason":""}', {
                "provider": "openai", "model": "test-model", "output_time_seconds": 0.2,
                "time_definition": "test", "token_consumption": {
                    "input_tokens": 10, "output_tokens": 4, "total_tokens": 14,
                },
            }),
            ('{"sql":"SELECT 1","confidence_level":"high","confidence_score":1,"reason":"fixed"}', {
                "provider": "openai", "model": "test-model", "output_time_seconds": 0.3,
                "time_definition": "test", "token_consumption": {
                    "input_tokens": 20, "output_tokens": 5, "total_tokens": 25,
                },
            }),
        ]
        dry_runs = [
            {"returncode": 1, "stdout": "", "stderr": "bad column"},
            {"returncode": 0, "stdout": "", "stderr": "", "estimated_bytes_processed": 0},
        ]
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(workflow, "call_model", side_effect=responses), \
             patch.object(workflow, "dry_run_query", side_effect=dry_runs):
            directory = Path(temporary) / "run"
            result = workflow.process_question(
                "test question", directory, self.config(),
                [{"table_name": "t", "column_name": "c"}], "schema", "q1",
            )
            self.assertEqual(result["status"], "completed")
            totals = result["metrics"]["llm_totals"]
            self.assertEqual(totals["calls"], 2)
            self.assertEqual(totals["input_tokens"], 30)
            self.assertEqual(totals["output_tokens"], 9)
            self.assertEqual(totals["total_tokens"], 39)
            self.assertEqual(totals["output_time_seconds"], 0.5)
            llm_steps = [step for step in result["metrics"]["steps"] if step["name"].startswith("llm_")]
            self.assertEqual(len(llm_steps), 2)
            self.assertEqual(llm_steps[0]["token_consumption"]["total_tokens"], 14)
            self.assertTrue((directory / "metrics.json").exists())
            self.assertTrue((directory / "attempts" / "attempt_02" / "dry_run.json").exists())

    def test_single_question_reports_progress_in_terminal_order(self):
        response = (
            '{"sql":"SELECT 1","confidence_level":"high",'
            '"confidence_score":1,"reason":""}',
            {
                "provider": "openai",
                "model": "test-model",
                "effort": "medium",
                "output_time_seconds": 4.08,
                "time_definition": "test",
                "token_consumption": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "total_tokens": 2,
                },
            },
        )
        config = {**self.config(), "effort": "medium", "execute": True}
        progress = MagicMock()
        execution = SimpleNamespace(returncode=0, stdout="answer\n1\n", stderr="")
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(workflow, "schema_query", return_value=([{"table_name": "t"}], "schema")), \
             patch.object(workflow, "call_model", return_value=response), \
             patch.object(workflow, "dry_run_query", return_value={"returncode": 0}), \
             patch.object(workflow, "execute_query", return_value=execution):
            result = workflow.process_question(
                "How many completed orders are there?",
                Path(temporary) / "run",
                config,
                progress=progress,
            )

        self.assertEqual(result["status"], "completed")
        events = [call.args for call in progress.call_args_list]
        self.assertEqual(
            [event[0] for event in events],
            ["SCHEMA", "SCHEMA", "QUESTION", "LLM", "LLM", "CHECK", "DB", "SAVE"],
        )
        self.assertEqual(events[2][1], "How many completed orders are there?")
        self.assertEqual(events[3][1], "Generating SQL (attempt 1/2)...")
        self.assertEqual(events[4][1], "Response received in 4.08s (confidence: high).")
        self.assertEqual(events[-1][1], "Query succeeded; saving answer.csv...")

    def test_terminal_log_has_timestamp_and_padded_category(self):
        output = StringIO()
        with redirect_stdout(output):
            workflow.terminal_log("RUN", "Starting single-question workflow.")
        self.assertRegex(
            output.getvalue(),
            re.compile(
                r"^\[\d{2}:\d{2}:\d{2}\] \[RUN   \] "
                r"Starting single-question workflow\.\n$"
            ),
        )

    def test_answer_command_prints_run_config_and_done_logs(self):
        config = {**self.config(), "effort": "medium", "execute": True}
        directory = Path("/tmp/single-question-result")
        result = {
            "status": "completed",
            "metrics": {"total_time_seconds": 6.31},
        }
        args = SimpleNamespace(
            question="How many completed orders are there?",
            workflow_dir=None,
        )
        output = StringIO()
        with patch.object(workflow, "config_from_args", return_value=config), \
             patch.object(workflow, "output_dir", return_value=directory), \
             patch.object(workflow, "process_question", return_value=result) as process, \
             patch.object(workflow, "datetime") as mocked_datetime, \
             redirect_stdout(output):
            mocked_datetime.now.return_value.strftime.return_value = "08:23:08"
            code = workflow.answer_command(args)

        self.assertEqual(code, 0)
        self.assertEqual(
            output.getvalue().splitlines(),
            [
                "[08:23:08] [RUN   ] Starting single-question workflow.",
                "[08:23:08] [RUN   ] All artifacts will be saved under /tmp/single-question-result",
                "[08:23:08] [CONFIG] Using openai/test-model, effort=medium.",
                "[08:23:08] [DONE  ] Completed with status 'success' in 6.31s.",
                "[08:23:08] [DONE  ] ",
            ],
        )
        process.assert_called_once_with(
            args.question, directory, config, progress=workflow.terminal_log
        )

    def test_cli_only_exposes_answer_and_batch_commands(self):
        help_text = workflow.build_parser().format_help()
        self.assertIn("{answer,batch}", help_text)
        self.assertNotIn("matrix", help_text.lower())

    def test_failure_still_saves_metrics_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(workflow, "call_model", side_effect=RuntimeError("provider unavailable")):
            directory = Path(temporary) / "failed"
            result = workflow.process_question(
                "test question", directory, self.config(),
                [{"table_name": "t", "column_name": "c"}], "schema", "q2",
            )
            self.assertEqual(result["status"], "failed")
            self.assertIn("provider unavailable", result["error"])
            metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
            metadata = json.loads((directory / "run_metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["status"], "failed")
            self.assertEqual(metadata["status"], "failed")
            self.assertIsNotNone(metrics["total_time_seconds"])

    def test_load_plain_text_questions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "questions.txt"
            path.write_text("first\n\nsecond\n", encoding="utf-8")
            questions = workflow.load_questions(path)
            self.assertEqual([item["question"] for item in questions], ["first", "second"])

    def test_execute_query_sets_independent_result_limit(self):
        with patch.object(workflow, "run_command") as run:
            workflow.execute_query("project", "US", "1000", 4321, "SELECT 1")
            command = run.call_args.args[0]
            self.assertIn("--max_rows=4321", command)
            self.assertIn("--maximum_bytes_billed=1000", command)

    def test_csv_data_row_count_handles_quoted_newlines(self):
        output = 'id,description\n1,"first line\nsecond line"\n2,plain\n'
        self.assertEqual(workflow.csv_data_row_count(output), 2)

    def test_effort_is_resolved_from_provider_specific_environment_variable(self):
        with patch.dict(
            "os.environ",
            {"OPENAI_EFFORT": "high", "ANTHROPIC_EFFORT": "low"},
            clear=False,
        ):
            self.assertEqual(workflow.resolve_effort("openai"), "high")
            self.assertEqual(workflow.resolve_effort("anthropic"), "low")

    def test_gemini_configuration_uses_provider_specific_environment_variables(self):
        with patch.dict(
            "os.environ",
            {"GEMINI_MODEL": "gemini-test", "GEMINI_THINKING_LEVEL": "medium"},
            clear=False,
        ):
            self.assertEqual(workflow.resolve_model("gemini", None), "gemini-test")
            self.assertEqual(workflow.resolve_effort("gemini"), "medium")

    def test_openai_effort_uses_reasoning_request_parameter(self):
        create = MagicMock(return_value=SimpleNamespace(output_text="ok", usage=None))
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        module = SimpleNamespace(OpenAI=MagicMock(return_value=client))
        with patch.dict(sys.modules, {"openai": module}):
            _, metadata = workflow.call_openai("prompt", "model", "high")
        create.assert_called_once_with(
            model="model", input="prompt", reasoning={"effort": "high"}
        )
        self.assertEqual(metadata["effort"], "high")

    def test_anthropic_effort_uses_output_config_request_parameter(self):
        response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="ok")], usage=None
        )
        create = MagicMock(return_value=response)
        client = SimpleNamespace(messages=SimpleNamespace(create=create))
        module = SimpleNamespace(Anthropic=MagicMock(return_value=client))
        with patch.dict(sys.modules, {"anthropic": module}):
            _, metadata = workflow.call_anthropic("prompt", "model", "low")
        create.assert_called_once_with(
            model="model",
            max_tokens=4096,
            messages=[{"role": "user", "content": "prompt"}],
            output_config={"effort": "low"},
        )
        self.assertEqual(metadata["effort"], "low")

    def test_gemini_uses_thinking_config_and_reports_usage(self):
        usage = SimpleNamespace(
            prompt_token_count=11,
            candidates_token_count=7,
            total_token_count=18,
        )
        response = SimpleNamespace(text="ok", usage_metadata=usage)
        generate = MagicMock(return_value=response)
        client = MagicMock()
        client.models = SimpleNamespace(generate_content=generate)
        client.__enter__.return_value = client
        client_factory = MagicMock(return_value=client)
        thinking_config = MagicMock(return_value="thinking-config")
        generate_config = MagicMock(return_value="generate-config")
        types_module = SimpleNamespace(
            ThinkingConfig=thinking_config,
            GenerateContentConfig=generate_config,
        )
        genai_module = SimpleNamespace(Client=client_factory, types=types_module)
        google_module = SimpleNamespace(genai=genai_module)
        with patch.dict(
            "os.environ", {"GEMINI_API_KEY": "test-key"}, clear=False
        ), patch.dict(
            sys.modules,
            {
                "google": google_module,
                "google.genai": genai_module,
                "google.genai.types": types_module,
            },
        ):
            _, metadata = workflow.call_gemini("prompt", "gemini-test", "high")
        client_factory.assert_called_once_with(api_key="test-key")
        client.__enter__.assert_called_once_with()
        client.__exit__.assert_called_once_with(None, None, None)
        thinking_config.assert_called_once_with(thinking_level="high")
        generate_config.assert_called_once_with(thinking_config="thinking-config")
        generate.assert_called_once_with(
            model="gemini-test",
            contents="prompt",
            config="generate-config",
        )
        self.assertEqual(metadata["token_consumption"]["total_tokens"], 18)


if __name__ == "__main__":
    unittest.main()
