# DATABASE IMPLEMENTATION PLAN AGENT
## System Architecture, Model Workflow & Implementation Specification

Version: 1.0

---

## 1. PURPOSE

The Database Implementation Plan Agent is an AI planning system whose ONLY primary responsibility is to convert a user's database requirement into the best practical database implementation plan.

It does NOT primarily execute database operations.

It analyzes the requirement, researches and retrieves relevant database knowledge, compares possible technologies, designs the data architecture, challenges the proposed design, validates it against the user's requirements, and produces a structured implementation plan.

Core principle:

USER REQUIREMENT
        ↓
UNDERSTAND
        ↓
RESEARCH
        ↓
COMPARE
        ↓
DESIGN
        ↓
CRITIQUE
        ↓
OPTIMIZE
        ↓
VALIDATE
        ↓
BEST DATABASE IMPLEMENTATION PLAN


---

# 2. PRIMARY RESPONSIBILITY

The agent must answer:

> "Given this application/data requirement, what is the best database architecture and how should it be implemented?"

It must NOT blindly recommend a database.

For every recommendation, it should determine:

- What data exists?
- How is the data related?
- How will the data be read?
- How will the data be written?
- What consistency is required?
- How much data exists?
- How fast will data grow?
- What is the expected traffic?
- What queries are important?
- What latency is required?
- What availability is required?
- What security is required?
- What compliance requirements exist?
- What is the budget?
- What infrastructure is available?
- What is the expected future scale?
- What operational complexity is acceptable?


---

# 3. HIGH-LEVEL FLOW

┌─────────────────────────────────────────────┐
│                    USER                     │
│        Database / Application Need          │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 1. REQUIREMENT ANALYZER                     │
│ Understand application and data requirements│
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 2. REQUIREMENT SPECIFICATION BUILDER        │
│ Convert natural language → structured spec  │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 3. KNOWLEDGE / RAG RETRIEVAL                │
│ Retrieve database technologies, patterns,   │
│ limitations, benchmarks, security practices │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 4. DATABASE CANDIDATE GENERATOR             │
│ SQL / NoSQL / NewSQL / Graph / Vector /     │
│ Time-Series / Analytical / Hybrid            │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 5. DATABASE COMPARISON ENGINE               │
│ Compare candidates against actual needs     │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 6. DATA MODEL DESIGNER                      │
│ Entities, relationships, schema, constraints│
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 7. ARCHITECTURE DESIGNER                    │
│ Indexing, scaling, replication, caching,    │
│ partitioning, HA, deployment                 │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 8. SECURITY & RELIABILITY DESIGNER          │
│ Authentication, authorization, encryption,  │
│ backup, disaster recovery, audit             │
└──────────────────────┬──────────────────────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 9. DATABASE CRITIC                           │
│ Find weaknesses, bottlenecks, bad decisions │
└──────────────────────┬──────────────────────┘
                       ↓
                 ┌─────┴─────┐
                 │           │
              PROBLEMS    ACCEPTABLE
                 │           │
                 ↓           ↓
             OPTIMIZE     VALIDATE
                 │           │
                 └─────┬─────┘
                       ↓
┌─────────────────────────────────────────────┐
│ 10. FINAL PLAN GENERATOR                    │
│ Produce implementation-ready database plan │
└──────────────────────┬──────────────────────┘
                       ↓
                     USER


---

# 4. AGENT INPUT

The model should receive a structured context rather than only a raw user message.

┌─────────────────────────────────────────────┐
│          DATABASE AGENT INPUT               │
├─────────────────────────────────────────────┤
│ 1. User Requirement                         │
│ 2. Application / Project Context            │
│ 3. Data Requirements                        │
│ 4. Expected Operations                      │
│ 5. Read / Write Patterns                    │
│ 6. Expected Data Volume                     │
│ 7. Expected Traffic                         │
│ 8. Performance / Latency Requirements       │
│ 9. Availability Requirements                │
│ 10. Consistency Requirements                │
│ 11. Security Requirements                   │
│ 12. Compliance Requirements                 │
│ 13. Budget / Infrastructure Constraints      │
│ 14. Growth Expectations                     │
│ 15. Existing Technology Constraints         │
│ 16. RAG Retrieved Database Knowledge        │
│ 17. Architecture Patterns                   │
│ 18. Database Limitations / Trade-offs       │
│ 19. Previous Design / User Feedback         │
│ 20. Validation / Critic Findings            │
└──────────────────────┬──────────────────────┘
                       ↓
                 DATABASE AGENT


---

# 5. REQUIREMENT ANALYZER

The first model stage extracts the actual problem.

Example:

User:

"Build a food delivery platform for 5 million users. Customers browse restaurants, place orders, make payments and track deliveries."

The analyzer converts this into:

{
  "domain": "food_delivery",
  "users": 5000000,
  "operations": [
    "user_registration",
    "restaurant_search",
    "menu_browsing",
    "order_creation",
    "payment",
    "delivery_tracking"
  ],
  "requirements": {
    "availability": "high",
    "order_consistency": "strong",
    "real_time": true,
    "read_heavy": true
  }
}

The agent must distinguish explicit requirements from assumptions.

If critical information is missing, the system should either:

1. Ask a targeted clarification question, OR
2. Make a clearly labelled assumption and continue.

It must never silently invent critical requirements.


---

# 6. REQUIREMENT SPECIFICATION

The natural-language requirement is converted into a canonical specification.

Recommended structure:

{
  "business_domain": "",
  "application_type": "",
  "entities": [],
  "relationships": [],
  "operations": [],
  "read_patterns": [],
  "write_patterns": [],
  "transaction_requirements": [],
  "data_volume": {},
  "growth_rate": {},
  "traffic": {},
  "latency": {},
  "availability": {},
  "consistency": {},
  "security": {},
  "compliance": {},
  "geography": {},
  "budget": {},
  "infrastructure": {},
  "future_requirements": [],
  "constraints": [],
  "assumptions": []
}


---

# 7. DATABASE KNOWLEDGE / RAG

The model should NOT be expected to memorize every database technology.

A database knowledge system should contain current, structured information about:

- PostgreSQL
- MySQL
- SQL Server
- Oracle
- SQLite
- CockroachDB
- YugabyteDB
- MongoDB
- DynamoDB
- Cassandra
- Redis
- Firebase / Firestore
- ClickHouse
- DuckDB
- Snowflake
- BigQuery
- Graph databases
- Vector databases
- Time-series databases
- Other relevant technologies

Each database knowledge record should include:

- database type
- data model
- strengths
- weaknesses
- consistency model
- transaction capabilities
- indexing
- partitioning
- replication
- sharding
- scaling
- high availability
- backup
- disaster recovery
- security
- query capabilities
- operational complexity
- cloud options
- cost characteristics
- common use cases
- anti-patterns
- migration considerations
- architecture patterns

RAG should retrieve only the information relevant to the current requirement.


---

# 8. DATABASE CANDIDATE GENERATION

The agent should first identify the database category.

Possible categories:

RELATIONAL
→ PostgreSQL, MySQL, SQL Server, Oracle

DISTRIBUTED SQL / NEWSQL
→ CockroachDB, YugabyteDB

DOCUMENT
→ MongoDB, Firestore

KEY-VALUE
→ Redis, DynamoDB

WIDE-COLUMN
→ Cassandra

ANALYTICAL
→ ClickHouse, DuckDB, BigQuery, Snowflake

GRAPH
→ Neo4j and similar systems

VECTOR
→ Vector databases / vector-enabled relational systems

TIME-SERIES
→ Time-series databases

HYBRID
→ Combination of multiple technologies

The agent should not compare every database in existence.

It should generate a small set of technically plausible candidates.


---

# 9. DATABASE COMPARISON ENGINE

Each candidate is evaluated against the user's actual requirements.

Example scoring dimensions:

┌───────────────────────────────┐
│ DATABASE EVALUATION           │
├───────────────────────────────┤
│ Functional fit                │
│ Data-model fit                │
│ Query fit                     │
│ Transaction fit               │
│ Consistency                   │
│ Read performance              │
│ Write performance             │
│ Scalability                  │
│ Availability                 │
│ Security                     │
│ Operational complexity       │
│ Cost                         │
│ Ecosystem                    │
│ Team expertise               │
│ Future growth                │
│ Migration flexibility        │
└───────────────────────────────┘

Weights must come from the requirement.

Example:

For banking:

Consistency = very high weight

For IoT:

Write throughput = very high weight

For analytics:

Analytical performance = very high weight

For a student project:

Cost + simplicity = high weight


---

# 10. DECISION ENGINE

The agent should produce:

1. Recommended database
2. Alternative database(s)
3. Score / reasoning
4. Why the winner is better for THIS requirement
5. When the alternative would be better
6. Important trade-offs

Example:

RECOMMENDATION:

PostgreSQL

WHY:

- Strong relational model
- ACID transactions
- Complex query support
- Mature indexing
- Strong ecosystem
- Good operational simplicity
- Suitable for current scale
- Can scale further with appropriate architecture

ALTERNATIVE:

CockroachDB

USE IF:

- Multi-region writes become a primary requirement
- Distributed SQL becomes more important than simplicity


---

# 11. DATA MODEL DESIGNER

After choosing the database, design the logical data model.

It should identify:

- entities
- attributes
- relationships
- cardinality
- primary keys
- foreign keys
- unique constraints
- nullable fields
- validation rules
- lifecycle/state fields

Example:

Users
    |
    | 1:N
    ↓
Orders
    |
    | N:1
    ↓
Restaurants


---

# 12. SCHEMA DESIGN

The agent should convert the logical model into a physical database design.

For SQL:

- tables
- columns
- data types
- primary keys
- foreign keys
- constraints
- indexes

For NoSQL:

- collections
- documents
- embedding
- referencing
- partition keys
- sort keys
- access patterns

The design must be based on actual access patterns rather than generic templates.


---

# 13. QUERY / ACCESS-PATTERN DESIGN

The agent must identify the most important operations.

Example:

1. Get user by ID
2. Get restaurant by location
3. Get restaurant menu
4. Create order
5. Get order status
6. Get user's order history

Then determine:

- required indexes
- query strategy
- expected query frequency
- caching requirements
- consistency requirements


---

# 14. PERFORMANCE ARCHITECTURE

The plan should determine whether the system needs:

- indexes
- composite indexes
- partitioning
- read replicas
- caching
- connection pooling
- batching
- asynchronous processing
- materialized views
- denormalization
- sharding
- CDN / edge strategies where relevant

The agent must avoid adding these automatically.

Every complexity must have a reason.


---

# 15. SCALING PLAN

The implementation plan should have stages.

Example:

STAGE 1 — INITIAL

Single primary database
+
automated backups
+
proper indexes

STAGE 2 — GROWTH

Read replicas
+
cache
+
connection pooling

STAGE 3 — HIGH SCALE

Partitioning
+
distributed architecture
+
specialized analytical store if required

STAGE 4 — GLOBAL SCALE

Multi-region architecture
+
regional data strategy
+
advanced failover


---

# 16. SECURITY DESIGN

The agent should include:

- authentication
- authorization
- least privilege
- database roles
- encryption in transit
- encryption at rest
- secret management
- network restrictions
- audit logging
- sensitive-data handling
- backup security
- access separation
- production/development isolation


---

# 17. BACKUP & DISASTER RECOVERY

The plan must specify:

- backup strategy
- backup frequency
- retention
- point-in-time recovery where applicable
- recovery objectives
- disaster recovery strategy
- restore testing
- regional failure strategy where required

The plan should distinguish:

RPO = acceptable data loss

RTO = acceptable recovery time


---

# 18. DATABASE CRITIC

This is a mandatory stage.

The first architecture is NOT automatically accepted.

The critic receives:

- original requirements
- selected database
- schema
- architecture
- scaling plan
- security plan
- retrieved knowledge

It asks:

1. Does the architecture satisfy every requirement?
2. Is the database selection justified?
3. Are critical indexes missing?
4. Are transactions correctly designed?
5. Is consistency appropriate?
6. Are there scalability bottlenecks?
7. Are there single points of failure?
8. Is the architecture unnecessarily complex?
9. Is the cost reasonable?
10. Is security sufficient?
11. Can the design migrate/grow later?
12. What assumptions are risky?

Output:

{
  "status": "REVISE",
  "issues": [
    {
      "severity": "HIGH",
      "issue": "Single database instance is a single point of failure",
      "recommendation": "Add HA configuration"
    }
  ]
}


---

# 19. OPTIMIZATION LOOP

┌──────────────────────────┐
│ Initial Architecture     │
└────────────┬─────────────┘
             ↓
┌──────────────────────────┐
│ Database Critic          │
└────────────┬─────────────┘
             ↓
      Issues detected?
        /          \
      YES           NO
       ↓             ↓
  Architecture    Validation
   Optimizer          ↓
       ↓          FINAL PLAN
       └──────→


The loop should stop when:

- all critical requirements are satisfied
- no high-severity architecture issue remains
- the design is internally consistent
- assumptions are explicitly identified
- further complexity has insufficient benefit


---

# 20. FINAL VALIDATION

The final validator checks:

REQUIREMENTS
✓ All user requirements addressed

DATABASE
✓ Database choice justified

DATA MODEL
✓ Entities and relationships addressed

PERFORMANCE
✓ Important access patterns addressed

SCALING
✓ Growth strategy defined

SECURITY
✓ Security requirements addressed

RELIABILITY
✓ Backup and recovery addressed

COST
✓ Cost considerations addressed

OPERATIONS
✓ Monitoring and maintenance addressed

TRADE-OFFS
✓ Major trade-offs documented

IMPLEMENTATION
✓ Clear implementation sequence provided


---

# 21. FINAL OUTPUT

The agent should produce a standardized document.

DATABASE IMPLEMENTATION PLAN

1. Executive Summary
2. Requirements Analysis
3. Assumptions
4. Recommended Database
5. Database Selection Reasoning
6. Alternative Options
7. System Architecture
8. Data Model
9. Schema Design
10. Relationships
11. Query / Access Patterns
12. Index Strategy
13. Transaction Strategy
14. Consistency Strategy
15. Performance Strategy
16. Scaling Strategy
17. Caching Strategy
18. Replication / High Availability
19. Partitioning / Sharding
20. Security Architecture
21. Backup & Disaster Recovery
22. Monitoring & Observability
23. Deployment Architecture
24. Migration Strategy
25. Cost Considerations
26. Risks
27. Trade-offs
28. Implementation Phases
29. Future Scaling Plan
30. Final Recommendation


---

# 22. MODEL WORKFLOW

The model should operate as a pipeline:

┌───────────────────────┐
│ GENERAL REASONING LLM │
│                       │
│ Requirement Analysis │
│ Planning              │
│ Architecture         │
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ DATABASE KNOWLEDGE RAG│
│                       │
│ Technologies          │
│ Patterns              │
│ Limitations           │
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ DATABASE COMPARATOR   │
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ ARCHITECTURE DESIGNER │
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ DATABASE CRITIC       │
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ ARCHITECTURE OPTIMIZER│
└──────────┬────────────┘
           ↓
┌───────────────────────┐
│ FINAL PLAN GENERATOR  │
└───────────────────────┘


---

# 23. RECOMMENDED MODEL STRATEGY

The system does not require a different model for every stage.

MVP:

General reasoning/coding model
+
RAG
+
structured prompts
+
critic loop

Recommended model family:

Qwen3.5-class model

Possible deployment modes:

LOCAL / LOW RESOURCE:
Qwen3.5-9B

HIGH QUALITY / HOSTED:
Qwen3.5-35B-A3B or an equivalent strong reasoning model

AGENT FRAMEWORK:
Qwen-Agent or another tool/agent framework

The model is responsible for reasoning.

The knowledge base is responsible for database-specific knowledge.

The validator/critic is responsible for challenging the design.


---

# 24. IMPORTANT DESIGN RULE

DO NOT BUILD:

User
 ↓
LLM
 ↓
"Use PostgreSQL"
 ↓
Final answer


BUILD:

User
 ↓
Requirement Analysis
 ↓
Structured Requirements
 ↓
Knowledge Retrieval
 ↓
Candidate Generation
 ↓
Candidate Comparison
 ↓
Database Selection
 ↓
Data Model
 ↓
Architecture
 ↓
Performance
 ↓
Security
 ↓
Critic
 ↓
Optimization
 ↓
Validation
 ↓
Implementation Plan


---

# 25. PROJECT DIRECTORY

DATABASE_AGENT/

├── agents/
│   ├── requirement_agent.json
│   ├── database_selection_agent.json
│   ├── architecture_agent.json
│   ├── schema_agent.json
│   ├── performance_agent.json
│   ├── security_agent.json
│   ├── critic_agent.json
│   └── final_plan_agent.json
│
├── knowledge/
│   ├── relational/
│   ├── nosql/
│   ├── distributed/
│   ├── analytical/
│   ├── graph/
│   ├── vector/
│   └── time_series/
│
├── policies/
│   ├── architecture_rules.json
│   ├── security_rules.json
│   ├── scaling_rules.json
│   └── design_constraints.json
│
├── schemas/
│   ├── requirement_schema.json
│   ├── database_evaluation_schema.json
│   ├── architecture_schema.json
│   ├── critic_schema.json
│   └── final_plan_schema.json
│
├── retrieval/
│   ├── retriever.py
│   ├── reranker.py
│   └── context_builder.py
│
├── planning/
│   ├── requirement_parser.py
│   ├── candidate_generator.py
│   ├── database_comparator.py
│   ├── architecture_designer.py
│   ├── optimizer.py
│   └── validator.py
│
├── prompts/
│   ├── requirement_prompt.txt
│   ├── selection_prompt.txt
│   ├── architecture_prompt.txt
│   ├── critic_prompt.txt
│   └── final_plan_prompt.txt
│
├── output/
│   └── implementation_plans/
│
└── app/
    └── main.py


---

# 26. EXAMPLE END-TO-END EXECUTION

USER:

"I want to build a healthcare application for 2 million users. Patients have profiles, appointments, prescriptions and medical records. Doctors need fast access to patient history. Medical data is sensitive. The application should be highly available."

↓

REQUIREMENT ANALYZER

Extracts:

- healthcare domain
- 2M users
- highly sensitive data
- patient history
- appointment transactions
- high availability
- doctor read patterns

↓

RAG

Retrieves:

- relational database patterns
- healthcare data considerations
- PostgreSQL security capabilities
- indexing patterns
- HA architecture
- backup/recovery practices

↓

CANDIDATE GENERATOR

Candidates:

- PostgreSQL
- MySQL
- distributed SQL option

↓

COMPARATOR

Evaluates each candidate according to:

- transactions
- consistency
- security
- query complexity
- availability
- scale
- operational complexity
- cost

↓

DATABASE SELECTION

Selects best candidate with justification.

↓

DATA MODEL

Designs:

Patients
Doctors
Appointments
Prescriptions
MedicalRecords

↓

ACCESS PATTERNS

Identifies:

- patient lookup
- doctor patient-history lookup
- appointment lookup
- prescription lookup

↓

PHYSICAL DESIGN

Designs:

- indexes
- constraints
- connection strategy
- replication
- partitioning if justified

↓

SECURITY

Designs:

- role separation
- least privilege
- encryption
- auditing
- secret management

↓

CRITIC

Finds:

"Patient-history queries may become expensive at scale."

↓

OPTIMIZER

Adds appropriate indexing / partitioning strategy if justified.

↓

VALIDATOR

Checks every original requirement.

↓

FINAL OUTPUT

Produces:

DATABASE IMPLEMENTATION PLAN

with architecture, schema, indexes, security, HA, backup, scaling, deployment and implementation phases.


---

# 27. WHAT MAKES THIS AGENT DIFFERENT

The product should NOT be marketed as:

"AI that recommends PostgreSQL."

It should be:

"AI that turns a real-world application requirement into a validated database architecture and implementation plan."

The intelligence comes from the complete pipeline:

REQUIREMENTS
+
DATABASE KNOWLEDGE
+
COMPARISON
+
DATA MODELING
+
ARCHITECTURE DESIGN
+
CRITIC
+
OPTIMIZATION
+
VALIDATION
=
DATABASE IMPLEMENTATION PLAN


---

# 28. SUCCESS CRITERIA

The agent is successful when the final plan:

1. Directly satisfies the user's requirements.
2. Selects a database based on evidence and requirements rather than popularity.
3. Explains why alternatives were rejected.
4. Provides a practical data model.
5. Addresses important access patterns.
6. Includes performance strategy.
7. Includes scaling strategy.
8. Includes security strategy.
9. Includes backup and recovery.
10. Identifies assumptions.
11. Identifies risks and trade-offs.
12. Has been challenged by an independent critic stage.
13. Avoids unnecessary complexity.
14. Provides a step-by-step implementation sequence.
15. Clearly explains how the design can evolve as the system grows.

FINAL PRINCIPLE:

The agent should optimize for the user's actual requirements, not for a particular database technology.

The output is not "the database."

The output is:

THE BEST JUSTIFIED DATABASE IMPLEMENTATION PLAN FOR THE GIVEN PROBLEM.
