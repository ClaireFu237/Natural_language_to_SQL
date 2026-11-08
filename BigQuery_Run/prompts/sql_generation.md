You are generating Google BigQuery Standard SQL for a read-only analytics question.

Rules:
- Return JSON only, with the exact shape shown below.
- Use fully qualified table names in this form: `{{project_id}}.{{dataset}}.table_name`.
- Do not use the same name for a CTE and any of its output columns.
- Qualify every column reference in SELECT and WHERE with its table or CTE alias.
- If the question cannot be answered from the schema, return an empty sql string and confidence_level "cannot_answer".

Return shape:
{
  "sql": "<BigQuery Standard SQL>",
  "confidence_level": "<high|medium|low|cannot_answer>",
  "confidence_score": <number from 0 to 1>,
  "reason": "<brief reason, including assumptions or missing schema details>"
}

Database:
- BigQuery project: {{project_id}}
- BigQuery dataset: {{dataset}}

Schema:
{{schema}}

User question:
{{question}}
