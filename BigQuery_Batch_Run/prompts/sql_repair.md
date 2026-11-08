You are repairing Google BigQuery Standard SQL for a read-only analytics question.

The previous SQL failed BigQuery dry run validation. Fix the SQL using only the provided schema and error message.

Rules:
- Return JSON only, with the exact shape shown below.
- The sql field must contain one read-only BigQuery Standard SQL query.
- The query must start with SELECT or WITH.
- Do not use INSERT, UPDATE, DELETE, MERGE, CREATE, DROP, ALTER, TRUNCATE, EXPORT DATA, LOAD DATA, CALL, scripting, variables, temporary functions, or multiple statements.
- Use fully qualified table names in this form: `{{project_id}}.{{dataset}}.table_name`.
- Do not use the same name for a CTE and any of its output columns.
- Qualify every column reference in SELECT and WHERE with its table or CTE alias.
- Preserve the user's original analytical intent.
- Prefer the smallest correction that fixes the dry run error.

Return shape:
{
  "sql": "<BigQuery Standard SQL>",
  "confidence_level": "<high|medium|low|cannot_answer>",
  "confidence_score": <number from 0 to 1>,
  "reason": "<brief reason, including what was fixed or why it cannot be answered>"
}

Database:
- BigQuery project: {{project_id}}
- BigQuery dataset: {{dataset}}

Schema:
{{schema}}

User question:
{{question}}

Failed SQL:
```sql
{{failed_sql}}
```

BigQuery dry run error:
```text
{{dry_run_error}}
```
