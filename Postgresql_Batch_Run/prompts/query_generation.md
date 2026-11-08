Given the database schema below, create one read-only Postgres SQL query that answers the user's question.

The configured target schema is `{{target_schema}}`.
Use only tables and other business objects from this target schema. Do not query
objects from any other schema, even when similarly named objects exist. Always
schema-qualify table names with `{{target_schema}}`.

Return JSON only with this exact shape:
{
  "sql": "<read-only postgres sql query>",
  "confidence_level": "<high|medium|low|cannot_answer>",
  "confidence_score": <number from 0 to 1>,
  "reason": "<brief reason>"
}

The SQL must start with SELECT or WITH. Do not include credentials, shell commands,
comments, DDL, DML, temporary tables, COPY, or transaction-control statements.
If the schema is insufficient, do not invent details: use confidence_level
"cannot_answer", an empty sql string, score 0, and explain what is missing.

Database schema:
{{schema}}

User question:
{{question}}
