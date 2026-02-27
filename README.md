# Porter Request Analytics System

A natural language analytics interface for porter request data that compiles user queries into **ClickHouse SQL** and returns structured statistical summaries.

The system combines **LLM-based query synthesis** with schema-aware validation and deterministic execution over a columnar analytical database.

---

## Problem Setting

Operational teams require ad hoc analytics on porter request workflows including turnaround time, request volume, and facility-level performance.

Traditional dashboards are insufficient for exploratory analysis due to rigid query templates. This system provides a flexible query interface while maintaining deterministic SQL execution and auditability.

---

## System Design

The architecture consists of four primary modules:

- Query compiler converting natural language into SQL
- Database execution layer over ClickHouse
- Result normalization and statistical summarization
- Interface layer exposing API and interactive visualization

---

## Core Capabilities

- Schema-aware NL → SQL compilation
- Turnaround time metric modeling
- Timezone-consistent timestamp handling
- Deterministic query validation
- Controlled row limiting for safe execution
- Structured result summarization
- Query logging for auditability

---

## Failure Modes

- Ambiguous natural language mapping  
- Schema drift sensitivity  
- Aggregation misinterpretation  
- LLM hallucinated joins

---

## Data Model

**Primary table:** `fact_porter_request`

### Key Fields

- Facility identifier
- Requester identifier
- Assigned porter identifier
- Scheduled timestamp
- Completion timestamp
- Workflow status

### Metric Definition

Turnaround time is computed as:

```sql
dateDiff('second', scheduled_time, completed_time)
```

---

## Architecture

```
User Query → Query Compiler → SQL Validator → ClickHouse Execution → Result Formatter
```

---

## Implementation Details

### Query Compilation

Natural language queries are translated into SQL using a schema-conditioned LLM prompt containing:

- Table schema
- Metric definitions
- Workflow semantics
- Query examples

The generated SQL is validated before execution.

---

### Database Layer

The execution layer provides:

- Connection lifecycle management
- Query timeout control
- Automatic row limiting
- Schema introspection

---

### Result Processing

Outputs are normalized to:

- Timezone-consistent timestamps
- Statistical aggregates
- Chart-ready tabular structures

---

## Security Considerations

- Environment-based credential management
- SQL validation prior to execution
- Read-only database access recommended
- Controlled result size limits

---

## Potential Extensions

- Query plan optimization
- Semantic caching
- Cost-aware query synthesis
- Schema evolution adaptation
- Reinforcement learning query refinement
