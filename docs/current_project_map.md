# Current Project Specification Map（当前项目规格地图）

> 审计日期：2026-08-13
>
> 审计范围：`E:/Kaifa/project 2026/chatbi-engine`
>
> 本文描述 Current State（当前真实状态），不是 Target Architecture（目标架构）；本轮 Repository Cleanup（仓库整理）、Sales Mart Metadata Rebuild（销售数据集市元数据重建）与 Sales Semantic Layer V1 重建后仍以实际代码、资源和验证结果为准。

## 1. Project Overview（项目概览）

ChatBI 当前是一个以 Course Baseline V1（课程基线 V1，旧基线）、当前 Sales Mart V1（销售数据集市第一版）及其可重复 Demo Data（演示数据）、Sales Semantic Layer V1（销售语义层第一版）、Schema Metadata（结构元数据）和既有离线检索资产为主的项目。当前 `resources/schema/` 的结构 Metadata（元数据）指向 PostgreSQL `mart_sales`；Course Baseline Metadata（课程基线元数据）已属于 Superseded/Legacy（替代/遗留）资产。

当前仓库没有发现 HTTP/API（接口）、UI（用户界面）、Application（应用层）、Domain（领域层）、LLM Client（大语言模型客户端）、SQL Generator（SQL 生成器）或 SQL Guard（SQL 安全防护）实现。现有运行入口主要是数据库初始化/生成/校验、当前 Semantic Contract 验证、遗留 Schema/Metric Offline Indexing（离线索引）和 TypeSpec Contract（接口类型规范契约）编译。

Git（版本控制）当前分支为 `master`。正式架构与工程文档已纳入版本控制；本地 IDE（集成开发环境）配置和临时文件不属于项目功能资产，也不作为 Source of Truth（事实源）。

## 2. Complete Project Tree（完整项目树）

大型目录折叠显示，但已确认其存在：

```text
chatbi-engine/
├── .git/                                  Git 元数据，已折叠
├── .idea/                                 本地 IDE（集成开发环境）配置，不纳入项目资产
├── .jbeval/datasets/                      空的评估数据目录
├── .model-cache/                          本地模型缓存目录，当前为空
├── .uv-cache/                             uv 缓存目录，文件量较大，已折叠
├── .venv/                                 项目 Python 虚拟环境，已折叠
├── data/
│   ├── postgres/                          PostgreSQL PGDATA 持久化目录
│   └── qdrant/
│       └── collections/
│           ├── metric_catalog/            Qdrant 派生索引目录
│           ├── schema_columns/            Qdrant 派生索引目录
│           └── schema_tables/             Qdrant 派生索引目录
├── database/
│   ├── grants.sql                         chatbi_app 只读权限脚本
│   ├── sales_mart/
│   │   └── 001_create_schema.sql          mart_sales 七表物理模型与约束
│   └── course_baseline/
│       ├── 001_create_tables.sql          五表建表脚本
│       ├── 002_seed_course_data.sql       小规模课程数据
│       ├── 003_validate_course_data.sql   结构/课程 SQL 校验
│       ├── 004_validate_large_data.sql    大数据质量/场景校验
│       └── business_scenarios.md         确定性数据场景说明
├── docs/
│   ├── Business/
│   │   ├── PRODUCT.md                     产品需求说明
│   │   └── Business Domain.md             销售业务领域说明
│   ├── Technical Design/
│   │   ├── ARCHITECTURE.md                系统架构设计基线
│   │   ├── ARCHITECTURE_DECISIONS.md      架构决策记录
│   │   ├── ENGINEERING.md                 工程设计与开发规范
│   │   ├── FEATURE_ARCHITECTURE_STANDARD.md 功能架构设计标准
│   │   ├── MODULE_CONTRACT_STANDARD.md    模块契约标准
│   │   ├── Natural Language Query/
│   │   │   └── ARCHITECTURE.md            自然语言查询功能架构
│   │   └── Platform Integration/
│   │       ├── Platform Integration SPEC.md  平台集成语义规格
│   │       ├── main.tsp                   TypeSpec 服务入口
│   │       ├── models.tsp                 TypeSpec 模型/事件
│   │       ├── operations.tsp             TypeSpec 操作/响应
│   │       ├── tspconfig.yaml              TypeSpec 编译配置
│   │       ├── package.json                TypeSpec Node 项目配置
│   │       ├── package-lock.json           Node 依赖锁定文件
│   │       ├── node_modules/               Node 依赖，已折叠且被忽略
│   │       └── generated/
│   │           └── openapi.2026-08-12.yaml OpenAPI 3.2 生成产物
│   └── current_project_map.md              当前状态与能力地图
├── models/
│   └── bge-m3/                            BAAI/bge-m3 本地模型，已折叠
├── resources/
│   ├── schema/
│   │   ├── tables.json                    表目录
│   │   ├── columns.json                   字段目录
│   │   └── relationships.json             PostgreSQL mart_sales 物理关系目录
│   └── semantic/sales/
│       └── metrics.json                   Sales Semantic Layer V1 指标目录
├── scripts/                               数据库/元数据验证脚本
│   ├── metadata/
│   │   └── export_schema.py                mart_sales 结构元数据导出
│   ├── course_baseline/
│   │   ├── init_database.py                Course Baseline 初始化/验证
│   │   ├── generate_demo_data.py           Course Baseline 大数据生成
│   │   ├── generate_schema.py              Course Baseline Schema 生成
│   │   └── validate_schema_relationships.py 关系资源校验
│   ├── sales_mart/
│   │   └── seed.py                         Sales Mart Demo Data 生成/加载/验证
├── tests/
│   ├── metadata/
│   │   └── test_schema_metadata.py         PostgreSQL 结构元数据测试
│   ├── semantic/
│   │   └── test_sales_semantic_resources.py Sales Semantic Layer V1 契约测试
│   └── sales_mart/
│       ├── test_schema.py                  Sales Mart Schema 测试
│       └── test_seed.py                    Demo Data Seed 测试
├── src/
│   ├── application/                       空目录，未发现源码
│   ├── bootstrap/                         空目录，未发现源码
│   ├── domain/                            空目录，未发现源码
│   ├── interfaces/                        空目录，未发现源码
│   └── infrastructure/retrieval/          当前唯一源码模块
├── .env                                   本地敏感环境变量，仅记录存在
├── .env.example                           安全环境变量模板
├── .gitignore                             忽略规则
├── AGENTS.md                              Agent（智能编码代理）贡献指南
├── docker-compose.yml                     PostgreSQL/Qdrant 容器配置
└── pyproject.toml                         Python/uv 项目元数据
```

未发现：`README.md`、`CHANGELOG.md`、`requirements.txt`、`Dockerfile`、`compose.yaml`、`evaluation/`、`infra/`、`.github/`、Kubernetes/Helm（编排/部署配置）、`prompts/`、`migrations/`。

## 3. Architecture Inventory（架构资产清单）

| 层或边界 | 当前实际内容 | 状态 |
|---|---|---|
| Product/Business（产品/业务） | `docs/Business/PRODUCT.md`、`docs/Business/Business Domain.md` | 文档存在 |
| Architecture（架构） | `docs/Technical Design/ARCHITECTURE.md` | 设计基线，不等同于实现 |
| Application（应用层） | `src/application/` 为空 | Not Found（未发现） |
| Domain（领域层） | `src/domain/` 为空；业务事实主要在文档和资源中 | Not Found（未发现源码） |
| Infrastructure（基础设施层） | `src/infrastructure/` | 旧 Retrieval 实现已移除，当前无源码 |
| Interfaces（接口层） | `src/interfaces/` 为空 | Not Found（未发现） |
| Bootstrap/Runtime（启动/运行时装配） | `src/bootstrap/` 为空；由脚本和 Docker Compose 分别启动 | Partial（部分存在） |
| Platform Contract（平台契约） | TypeSpec 源文件和 OpenAPI 生成文件 | 契约存在，服务实现不存在 |

## 4. Key Files（关键文件职责）

### 4.1 配置与容器

| 文件 | 类型/所属 | 主要职责与关系 |
|---|---|---|
| `.env` | Environment（环境变量） | 本地实际配置；包含数据库、LLM、Qdrant、RAG 参数和值。值未读取、未输出。 |
| `.env.example` | 配置模板 | 覆盖当前 Compose、数据库脚本、Qdrant 和 BGE-M3 离线脚本实际消费的配置；不声明未被代码消费的 LLM/RAG 变量。 |
| `docker-compose.yml` | Docker Compose（容器编排） | 配置 `postgres:16-alpine` 与 `qdrant/qdrant`；挂载 `data/postgres`、`data/qdrant`；暴露 5433、6333、6334。 |
| `pyproject.toml` | Python/uv 配置 | 项目名 `chatbi-engine`、版本 `0.1.0`、Python `>=3.11`；声明 4 个 Python 直接依赖。 |
| `AGENTS.md` | 工程规则 | Agent 行为、架构边界、Source of Truth（事实源）和安全规则；不是业务实现。 |

### 4.2 数据库与数据脚本

| 文件 | 所属 | 输入/输出与职责 |
|---|---|---|
| `database/course_baseline/001_create_tables.sql` | Database（数据库） | 删除并重建 `public` 下 5 张课程表。包含 5 个主键、2 个外键、`sales_orders.order_no` 唯一约束和汇率复合主键。 |
| `database/sales_mart/001_create_schema.sql` | Database（数据库） | 幂等创建 `mart_sales` Schema（模式）及 7 张 Sales Mart V1 表，包含 SCD2、事实完整性、PK/FK、唯一约束和 V1 索引；不修改 `public`。 |
| `scripts/sales_mart/seed.py` | Database/Data Seed（数据库/数据种子） | 使用固定 seed 生成并加载 2024-01-01 至 2025-12-31 的 Sales Mart Demo Data，支持 `--reset`，自动输出行数/状态/币种/指标并验证业务不变量。 |
| `tests/sales_mart/test_seed.py` | Database Test（数据库测试） | 验证固定 seed、规模、SCD2、状态事实、reset + reseed 和 PostgreSQL 业务校验；保留最后一次有效 Demo Data。 |
| `002_seed_course_data.sql` | Database/Seed（数据库/种子） | 写入人工可读的小规模课程数据。 |
| `003_validate_course_data.sql` | Database/Test（数据库/校验） | 校验表集合、孤儿记录、汇率、金额、数量、日期、费用等结构/数据条件，并执行课程查询。 |
| `004_validate_large_data.sql` | Database/Evaluation（数据库/评估） | 校验大数据行数、质量检查、年度/季度/区域/费用等业务场景。 |
| `database/grants.sql` | Security/Database（权限/数据库） | 创建或更新 `chatbi_app`，设置 `NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOBYPASSRLS`，只授予 5 张表 `SELECT`。 |
| `scripts/course_baseline/init_database.py` | Offline/Database CLI（离线数据库命令行） | 使用 migrator 配置创建 `chatbi_mvp`、执行课程 SQL、读取元数据、输出行数/约束/5 类课程验证。可能执行建库、建表和写入。 |
| `tests/sales_mart/test_schema.py` | Database Test（数据库测试） | 重复执行 Sales Mart DDL，验证 7 张表、PK/FK、SCD2、Completed 完整性、状态/汇率/粒度约束；测试业务行全部事务回滚。 |
| `scripts/course_baseline/generate_demo_data.py` | Offline/Data Generation（离线数据生成） | 使用 seed、日期和数量参数生成确定性大数据；只允许目标数据库 `chatbi_mvp`，对 5 张表执行清空、批量写入、质量和业务场景校验。 |
| `scripts/metadata/export_schema.py` | Offline/Metadata Export（离线元数据导出） | 一次只读连接扫描 PostgreSQL `mart_sales`，构造 Canonical Schema Model（统一结构模型），再投影当前 7 张表的 `tables.json`、`columns.json`、物理 `relationships.json`。 |
| `tests/metadata/test_schema_metadata.py` | Metadata Test（元数据测试） | 直接读取 PostgreSQL 系统元数据核对当前三份 JSON 的表、字段、类型、可空性、PK/UNIQUE/FK、角色日期 FK、SCD2 物理对象和重复导出稳定性。 |
| `scripts/course_baseline/generate_schema.py` | Legacy Offline/Metadata Generation（遗留离线元数据生成） | 仅属于旧 Course Baseline；仍保留原代码，不作为当前 Sales Mart Metadata 的生成器，也不作为当前 `resources/schema/` 事实源。 |

### 4.3 资源验证脚本

| 文件 | 所属层 | 主要职责与上下游 |
|---|---|---|
| `scripts/course_baseline/validate_schema_relationships.py` | Test/CLI（测试/命令行） | 不依赖数据库验证关系资源版本、PK/UNIQUE/FK 和人工语义关系。 |

## 5. Entry Points（系统入口）

| 入口 | 调用链 | 当前性质 |
|---|---|---|
| `scripts/course_baseline/init_database.py` | `.env` → psycopg → `chatbi_mvp` → 课程建表/小数据/验证 | 离线数据库维护入口 |
| `scripts/metadata/export_schema.py` | `.env` → 一次 psycopg 只读连接 → `mart_sales` 系统元数据 → Canonical Schema Model → 三份 JSON | 当前 Sales Mart Schema Metadata 导出入口 |
| `tests/metadata/test_schema_metadata.py` | PostgreSQL 只读元数据核对 → 三份 JSON、约束、稳定性 | 当前 Sales Mart Schema Metadata 验证入口 |
| `tests/sales_mart/test_schema.py` | `.env` → psycopg → `mart_sales` DDL → 15 项 PostgreSQL Schema Test（结构测试） | Sales Mart V1 Schema 验证入口 |
| `scripts/sales_mart/seed.py` | 参数/`.env` → 确定性生成 → `mart_sales` Transaction（事务）→ 业务验证/指标报告 | Sales Mart V1 Demo Data 入口 |
| `tests/sales_mart/test_seed.py` | 纯生成测试 + PostgreSQL reset/reseed 集成测试 | Demo Data 回归入口 |
| `scripts/course_baseline/generate_demo_data.py` | 参数/`.env` → psycopg → 5 表清空与批量写入 → 质量/场景检查 | 离线数据生成入口 |
| `scripts/course_baseline/generate_schema.py` | 旧 Course Baseline PostgreSQL 元数据 → 旧 Schema 文本/JSON 目录 | 遗留结构生成入口，不参与当前 Sales Mart Metadata |
| `tests/semantic/test_sales_semantic_resources.py` | Semantic JSON → Contract Test → Schema Metadata mapping/dependency checks | 当前 Sales Semantic Layer V1 确定性验证入口 |
| `npm run compile`（工作目录为 Platform Integration） | TypeSpec → Compiler（编译器）→ OpenAPI 3.2 YAML | 契约生成入口 |
| API/CLI/UI/Worker | 未发现实现 | Not Found（未发现） |
| Docker Compose | 配置了 PostgreSQL/Qdrant 服务，但本次运行状态未确认 | 容器配置入口，不是业务 API 入口 |

## 6. Runtime Environment（运行环境）

### 已确认的工具

- Windows 工作树：`E:/Kaifa/project 2026/chatbi-engine`
- Python：`3.11.15`
- uv：`0.12.2`
- Node.js：`24.15.0`
- npm：`12.0.2`
- Docker 客户端存在，但 Docker API 连接检查因权限不足失败。
- `.venv/` 存在；其 Python 版本为 3.11.15。
- 当前 `pyproject.toml` 声明 4 个 Python 直接依赖，根目录存在 `uv.lock`；`uv sync` 已在项目 `.venv` 中完成安装。
- 当前项目 `.venv` 已安装 `psycopg`、`langchain-core`、`qdrant-client`、`FlagEmbedding` 及其传递依赖；导入冒烟测试通过。

### Docker Compose（容器编排）配置

| 服务 | 容器名 | 镜像 | 端口 | 持久化 | 当前状态 |
|---|---|---|---|---|---|
| PostgreSQL | `chatbi-engine-postgres` | `postgres:16-alpine` | 宿主 `5433` → 容器 `5432` | `./data/postgres` | 旧 Course Baseline 生成器使用 `chatbi_app`；当前 Sales Mart Metadata Exporter 使用本地 `.env` 的只读元数据查询配置；Docker 容器进程状态未通过 Docker API 确认 |
| Qdrant | `chatbi-engine-qdrant` | `qdrant/qdrant` | `6333` REST、`6334` gRPC | `./data/qdrant` | `/healthz`、Schema/Metric 索引和重复构建验证通过；Docker 容器进程状态未通过 Docker API 确认 |

### Environment（环境变量）

`.env` 存在但值未输出。已确认的变量名包括：

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_MIGRATOR_USER
POSTGRES_MIGRATOR_PASSWORD=<secret>
POSTGRES_APP_USER
POSTGRES_APP_PASSWORD=<secret>
LLM_MODEL
LLM_API_KEY=<secret>
LLM_BASE_URL
LLM_TEMPERATURE
LLM_SEED
LLM_TIMEOUT_SECONDS
LLM_ENABLE_THINKING
QDRANT_URL
QDRANT_API_KEY=<secret>
QDRANT_COLLECTION_ALIAS
RAG_EMBEDDING_MODEL
RAG_MODEL_SOURCE
RAG_EMBEDDING_DIMENSION
RAG_EMBEDDING_BATCH_SIZE
RAG_EMBEDDING_DEVICE
RAG_QDRANT_TIMEOUT_SECONDS
QUERY_CONTEXT_MODE
RAG_CONTEXT_MAX_CHARACTERS
```

`.env.example` 仍保留历史 BGE/Qdrant 参数模板；当前源码没有旧 Retrieval 实现的运行时消费者。LLM/RAG 配置仍因没有代码消费者而未加入模板。

## 7. External Dependencies（外部依赖）

| 依赖 | 用途 | 配置来源 | 运行时要求/部署形态 |
|---|---|---|---|
| PostgreSQL | Course Baseline 数据库、元数据读取、数据生成和校验 | `.env`、`docker-compose.yml`、`database/`、`psycopg` 脚本 | Schema 元数据生成已通过；Docker 容器进程状态未通过 Docker API 确认 |
| Qdrant | 历史 Dense/Sparse 向量持久化资产与本地服务配置 | `.env`、`docker-compose.yml`、`data/qdrant/` | 资产与配置保留；旧索引代码已移除，本轮未修改 Docker 服务状态 |
| BAAI/bge-m3 | 本地模型资产 | `.env.example`、`models/bge-m3` | 模型目录保留；旧 Embedding 适配器已移除，当前无代码消费者 |
| FlagEmbedding | 历史 Embedding 依赖声明 | `pyproject.toml` | 仍在依赖文件中声明；当前无源码消费者 |
| LangChain Core | 历史 `Document` 依赖声明 | `pyproject.toml` | 仍在依赖文件中声明；当前无源码消费者 |
| qdrant-client | 历史 Qdrant 客户端依赖声明 | `pyproject.toml` | 仍在依赖文件中声明；当前无源码消费者 |
| psycopg | PostgreSQL 连接和 SQL 执行 | 三个数据库脚本 | Python 直接依赖，已在 `pyproject.toml` 声明 |
| TypeSpec | API Contract（API 契约）编译 | Platform Integration `package.json`/`package-lock.json` | Node 子项目依赖；本地 `node_modules` 存在 |
| Docker | PostgreSQL/Qdrant 容器运行 | `docker-compose.yml` | 外部本机服务；本次 API 权限检查失败 |
| LLM Provider（大模型供应商） | `.env` 有配置名 | 未发现 Python/Node 消费者 | 仅配置存在，实际调用未确认，代码中未发现 |
| FastAPI、Streamlit、LangGraph、Redis、MySQL、ChromaDB、Elasticsearch、Kubernetes、Helm | 未发现实际源码/配置 | — | Not Found（未发现） |

## 8. Database & Data Assets（数据库与数据资产）

### 物理数据库基线

`database/course_baseline/001_create_tables.sql` 定义且 `scripts/course_baseline/init_database.py` 期望严格存在以下 5 张表：

- `dim_customers`
- `dim_products`
- `sales_orders`
- `exchange_rates`
- `finance_expenses`

结构关系：

- 5 个主键；`exchange_rates` 为 `(rate_date, currency)` 复合主键。
- 2 个外键：`sales_orders.customer_id → dim_customers.customer_id`、`sales_orders.product_id → dim_products.product_id`。
- `sales_orders.order_no` 为唯一约束。
- SQL 中没有 `dim_date`、`dim_currency`、`dim_employee`、`dim_sales_territory` 或销售额/毛利/成本人民币派生字段。

生成器默认目标和规模：

- 数据库：`chatbi_mvp`
- `dim_customers`：500
- `dim_products`：150
- `sales_orders`：30,000
- `exchange_rates`：3,288
- `finance_expenses`：216
- 日期：2024-01-01 至 2026-12-31；币种 CNY、USD、EUR；费用按 2024-01 至 2026-12。
- 随机种子默认 `42`。

这些是脚本目标和校验条件；本次通过 `chatbi_app` 成功读取并验证了 PostgreSQL Schema 元数据，但没有把当前数据库行数作为关系资源事实源。

### Sales Mart V1 物理模型

`database/sales_mart/001_create_schema.sql` 创建独立的 `mart_sales` Schema（模式），包含且仅包含以下 7 张表：

- `dim_date`
- `dim_customer`
- `dim_product`
- `dim_sales_region`
- `dim_currency`
- `fct_exchange_rate_daily`
- `fct_sales_order_line`

该 DDL（数据定义语言）已在配置的 `chatbi_mvp` PostgreSQL 数据库中重复执行验证；`tests/sales_mart/test_schema.py` 的 15 项自动化测试全部通过，测试业务行在事务结束时回滚。随后由 Demo Data Seed（演示数据种子）加载器写入可重复数据；`public` Schema 仍为原有 5 张表。

模型边界：`fct_sales_order_line` 一行对应一条订单明细；Customer/Product 使用 SCD Type 2（第二型缓慢变化维度）；默认业务时间和 FX Date（汇率日期）均为 Completion Date（完成日期）；销售事实冻结 CNY（人民币）销售额、汇率和成本；Gross Profit / Gross Margin（毛利 / 毛利率）不物理存储；Return Fact（退货事实）未建设。

### Sales Mart V1 Demo Data

`scripts/sales_mart/seed.py --reset --seed 42` 已实际加载并验证一套可重复 Demo Data：

- 200 个客户业务键、224 行 Customer SCD2 版本；
- 80 个产品业务键、90 行 Product SCD2 版本；
- 6 个销售区域、4 个币种、731 天日期；
- 2,924 条每日汇率、5,000 个销售订单、11,198 条销售订单明细；
- 明细状态：Completed 8,380、Confirmed 1,219、Pending 834、Cancelled 765；
- 交易币种明细：CNY 7,556、USD 1,668、EUR 1,200、JPY 774。

当前已验证 Demo Data 指标：Completed Sales Quantity（已完成销量）`81,818.419360`，Sales Revenue CNY（人民币销售额）`1,285,634,448.378276`，Sales Cost CNY（人民币销售成本）`943,197,788.784322`，Gross Profit（毛利）`342,436,659.593954`，Gross Margin（毛利率）约 `26.64%`。2025 年完成销售额高于 2024 年；存在 49 条负毛利明细和 143 条低毛利明细，用于后续分析验证。

`scripts/sales_mart/seed.py` 使用单事务加载；失败自动回滚。`--reset` 只清理 `mart_sales` 业务数据，不执行 `DROP`，不修改 `public`。当前 `public` 五张旧基线表行数仍为 `dim_customers=500`、`dim_products=150`、`sales_orders=30,000`、`exchange_rates=3,288`、`finance_expenses=216`。

### 权限脚本

`database/grants.sql` 是 `chatbi_app` 只读角色初始化/校验边界：撤销建库、建角色和写表权限，仅授予 5 张表的 `SELECT`，并设置 `NOBYPASSRLS`。这是权限配置脚本，不代表本次已从运行中的数据库重新验证。

### Schema Metadata（结构元数据）

- 当前物理结构事实源是 PostgreSQL `mart_sales`，不是 DOMAIN_SPEC（领域规格）、ANALYTICAL_MODEL（分析模型）或旧 Course Baseline 资源。
- `resources/schema/tables.json`：从 PostgreSQL COMMENT（注释）和表目录导出的 7 个 `mart_sales` 表对象。
- `resources/schema/columns.json`：从 PostgreSQL 实际字段元数据导出的 69 个字段对象，保留真实 `data_type`、可空性、默认值和字段注释。
- `resources/schema/relationships.json`：`schema_version=1` 的物理关系目录，包含 7 个 PK、7 个 UNIQUE、9 个 FK 和 2 个独立唯一索引；不包含 `semantic_relationships`。
- `scripts/metadata/export_schema.py`：一次 PostgreSQL 只读连接 → Canonical Schema Model（统一结构模型）→ 三份 JSON 投影；只执行元数据 `SELECT`。
- `tests/metadata/test_schema_metadata.py`：对 PostgreSQL 实际结构、当前三份 JSON 和重复导出内容哈希执行确定性验证。
- 下游机器可读资源固定为 `tables.json`（Table Metadata / Table Retrieval）、`columns.json`（Column Metadata / Field Retrieval）、`metrics.json`（Metric Catalog / Metric Retrieval）和 `relationships.json`（Relationship Catalog / Join Graph）；不建立独立 `dimensions.json` 或 `field_semantics.json`。
- `resources/schema/course_schema.txt`：已从活动资源中删除；它属于旧 Course Baseline，可由遗留生成器重新产生，但不是当前 Sales Mart Metadata。

`scripts/course_baseline/generate_schema.py` 与 `scripts/course_baseline/validate_schema_relationships.py` 仍只服务旧 Course Baseline；本次没有修改它们，也没有让它们生成当前 Sales Mart Metadata。

## 9. AI / LLM Assets（AI/大模型资产）

- 本地 `models/bge-m3/` 目录存在完整模型文件，包括 PyTorch（深度学习框架）模型、Tokenizer（分词器）和 Sparse/Dense 相关文件。
- `models/bge-m3/` 本地模型目录保留，但旧 `BGE-M3` 适配器和模型测试入口已移除。
- `.env` 存在 `LLM_*` 配置名，但源码未发现 LLM Client、模型调用、Prompt Builder（提示词构建）或 SQL 生成消费者。
- 未发现 Prompt 文件、系统提示词资源、LLM Evaluation（大模型评估）数据或模型网关实现。

## 10. Semantic & RAG Assets（语义与检索增强资产）

当前存在 Sales Mart 物理 Metadata（结构元数据）和 Sales Semantic Layer V1；既有离线目录/索引属于 Legacy / Pending Refactor（遗留 / 待重构）边界，本次没有重建 Retrieval（检索）、BGE-M3 或 Qdrant：

```text
PostgreSQL mart_sales
        ↓
scripts/metadata/export_schema.py
        ↓
tables.json / columns.json / relationships.json

resources/semantic/sales/
└── metrics.json

历史 BGE-M3 模型与 Qdrant 持久化资产（本次未删除）
```

- `metrics.json` 是当前 Sales Semantic Layer V1 的 Metric Catalog（指标目录），定义 5 个核心指标；Customer、Product、Time、Region 等业务 Dimension（维度）继续由 DOMAIN_SPEC / ANALYTICAL_MODEL 定义，并通过 Column / Field Matching（列 / 字段匹配）解析，不建立独立维度资源。
- 当前 `relationships.json` 只记录 PostgreSQL Physical Relationship Catalog（物理关系目录），没有 `semantic_relationships`；它不进入 Retrieval Record（检索记录）、Embedding（向量化）或 Vector Index（向量索引）。确定性 Relationship Graph / Join Resolver（关系图 / 连接解析器）是后续在线能力的目标边界，当前仓库尚无运行时实现。
- 旧 Loader、Embedding 适配器和 Qdrant 索引构建代码已移除；历史 `data/qdrant/` 持久化目录未删除。当前 Schema Metadata 的 7 张表、69 个字段均已从 PostgreSQL COMMENT 导出非空 description；本次未修改数据库或 `resources/schema/`。
- `data/qdrant/collections/` 的历史持久化目录未作为当前 Offline Pipeline V1 的实现证明；本次未重建或修改其中内容。
- 没有 Hybrid Search（混合检索）、RRF（倒数排名融合）、Reranker（重排器）、在线 Retriever（检索器）或 LangChain Qdrant 集成。

## 11. Online Pipeline（在线运行链路）

当前没有真实的在线用户查询链路。未发现 API/UI/CLI 查询入口，只有离线脚本。

```text
User Request（用户请求）                 未发现入口
        ↓
Table/Column/Metric Retriever            未发现在线封装
        ↓
Schema Linking / Metric Context          未发现
        ↓
Prompt Builder / LLM                     未发现
        ↓
SQL Generation / SQL Guard               未发现
        ↓
PostgreSQL Query Executor                未发现在线 Adapter
        ↓
Result Formatter / API / UI              未发现
```

`QdrantStore.query_dense()`、`query_sparse()` 和 `retrieve()` 存在，但当前只被离线索引脚本用于 smoke query（冒烟查询）或按已知 Point ID 读取，不能确认其构成在线 Retriever。

## 12. Offline Pipeline（离线链路）

### 数据库链路

```text
.env
  → psycopg
  → 创建/连接 chatbi_mvp
  → 执行 001/002/003 SQL
  → 结构、行数、课程查询校验
```

大数据链路为：

```text
seed=42 + 日期/数量参数
  → 生成客户、产品、汇率、订单、费用
  → 校验 5 表结构
  → TRUNCATE 5 表
  → 批量写入
  → 质量检查 + 业务场景检查
  → 事务提交或回滚
```

### Current Semantic Layer Validation（当前语义层验证链路）

```text
DOMAIN_SPEC / ANALYTICAL_MODEL
  → resources/semantic/sales/metrics.json
  → tests/semantic/test_sales_semantic_resources.py
  → mart_sales tables/columns/relationships mapping checks
```

### Legacy Offline Indexing（遗留离线索引链路）

```text
旧 JSON Contract
  → Legacy Loader
  → LangChain Document
  → BGE-M3 / Qdrant
```

该链路未因本次 Semantic Layer V1 重建而运行或更新；当前 V1 与旧 Loader 之间的适配属于 Pending Offline Pipeline Refactor（待离线链路重构）。

### API 契约链路

```text
main.tsp + models.tsp + operations.tsp
  → TypeSpec Compiler
  → @typespec/openapi3
  → docs/Technical Design/Platform Integration/generated/openapi.2026-08-12.yaml
```

## 13. API & Contracts（API 与契约）

Platform Integration（平台集成）目录存在正式 TypeSpec 契约：

- `main.tsp`：服务名、Bearer Authentication（Bearer 身份认证）、API 版本 `2026-08-12`。
- `models.tsp`：`RunRequest`、`RunResponse`、`RunOutcome`、`QueryResult`、`AnalysisResult`、`Clarification`、`UnsupportedRequest`、`ErrorResponse`、SSE 事件模型。
- `operations.tsp`：`POST /runs` 阻塞执行和 `POST /runs/stream` SSE Streaming（服务器发送事件流）；使用 `api-version` 查询参数和 400/401/403/500/503/504 错误响应。
- `RunStreamEvents` 包含 `started`、`delta`、`completed`、`failed`；后两者在 TypeSpec 中标记为 Terminal Event（终止事件）。
- `tspconfig.yaml`：只生成 OpenAPI 3.2 YAML 到 `generated/openapi.{version}.yaml`，并启用 `warn-as-error`。
- `docs/Technical Design/Platform Integration/generated/openapi.2026-08-12.yaml`：实际存在，首行为 `openapi: 3.2.0`，包含两个 POST 路径、Bearer 安全方案和 SSE `itemSchema`。

TypeSpec 是正式 API Contract Source of Truth（接口契约事实源），OpenAPI 是 Generated Artifact（生成产物）。SPEC 文档记录集成语义。当前 TypeSpec 1.14.0 的 OpenAPI emitter（生成器）对携带 Model Payload（模型载荷）的 Terminal Event 生成信息不完整，SPEC 已明确记录该限制。

没有发现与上述契约对应的 FastAPI、HTTP Server（HTTP 服务）、Controller（控制器）或运行时 API 实现。

## 14. Tests & Evaluation（测试与评估）

当前存在 `tests/metadata/`、`tests/semantic/` 和 `tests/sales_mart/` 目录，但未发现统一测试框架配置或持续集成测试；前者包含当前 Sales Mart Schema Metadata Test（结构元数据测试），`tests/semantic/` 包含当前 Sales Semantic Layer V1 Contract Test（语义层契约测试），后者包含 Sales Mart Schema Test（数据集市结构测试）和 Demo Data Seed Test（演示数据种子测试）。

当前实际验证资产：

| 资产 | 验证内容 | 类型 |
|---|---|---|
| `003_validate_course_data.sql` | 五表结构、约束、课程查询和基础数据条件 | Database Validation（数据库校验） |
| `004_validate_large_data.sql` | 大数据质量、年度/季度/区域/费用场景 | Business Acceptance（业务验收脚本） |
| `scripts/course_baseline/init_database.py` | 建库后行数、PK/FK/UNIQUE、课程 SQL | Integration-like CLI（集成式命令行校验） |
| `tests/sales_mart/test_schema.py` | `mart_sales` 7 表、PK/FK、SCD2、事实约束和成功写入；测试业务行回滚 | Database Schema Test（数据库结构测试） |
| `tests/metadata/test_schema_metadata.py` | PostgreSQL `mart_sales` 7 表、69 字段、真实类型/可空性、PK/UNIQUE/FK、角色日期 FK、SCD2 物理对象和重复导出哈希 | Schema Metadata Test（结构元数据测试） |
| `tests/semantic/test_sales_semantic_resources.py` | 5 个指标、15 个维度、依赖无环、当前物理映射、默认时间、完成过滤、业务边界和 FK 目录不重复 | Semantic Contract Test（语义契约测试） |
| `tests/sales_mart/test_seed.py` | 固定 seed、规模、SCD2、状态、reset/reseed、指标与 public 边界；留下最后一次有效 Demo Data | Database Seed Test（数据库种子测试） |
| `.jbeval/datasets/` | 目录存在但当前为空 | Evaluation Dataset（评估数据集）未发现 |

除上述数据库结构/种子测试脚本外，仍未发现统一 Unit Test（单元测试）/Contract Test（契约测试）框架、Retrieval Evaluation（检索评估）、SQL Evaluation（SQL 评估）、End-to-End Evaluation（端到端评估）或 Bad Case Replay（失败案例回放）资产。

## 15. Deployment & Docker（部署与容器）

- 只有 `docker-compose.yml`，配置本地 PostgreSQL 和 Qdrant。
- 没有 Dockerfile、Kubernetes、Helm、CI/CD 或部署脚本。
- `data/postgres/` 是 PostgreSQL 数据目录，存在 `PG_VERSION`、`postmaster.pid` 等 PGDATA 文件；文件存在不能证明服务当前运行。
- `data/qdrant/` 有 Qdrant 持久化结构和三个 Collection 目录。
- 本轮 Schema Metadata 导出与重复内容哈希、Sales Mart Metadata Test 已通过；没有重建或修改 Qdrant、BGE-M3 或 Retrieval 索引。
- Docker 容器生命周期状态未独立审计；不能仅凭持久化目录判断容器当前运行状态。

## 16. Documentation Map（文档地图）

| 文档 | 类型 | 当前作用/事实边界 |
|---|---|---|
| `AGENTS.md` | Contributor Guide（贡献指南） | Agent 开发约束；不是架构或业务事实源。 |
| `docs/Business/PRODUCT.md` | Product Requirement（产品需求） | 产品目标、用户、自然语言查询和经营分析范围。 |
| `docs/Business/Business Domain.md` | Business Domain（业务领域） | 销售对象、指标、口径、维度和领域边界；文档内部将 `SALES_DOMAIN.md` 作为名称，但实际文件名是 `Business Domain.md`。 |
| `docs/Technical Design/ARCHITECTURE.md` | Architecture（架构） | 系统定位、责任边界、分层、依赖和不变量；设计基线，不代表代码已实现。 |
| `docs/Technical Design/ARCHITECTURE_DECISIONS.md` | Architecture Decision（架构决策） | 记录系统级关键架构选择、原因、影响和重新评估条件。 |
| `docs/Technical Design/ENGINEERING.md` | Engineering Baseline（工程基线） | 定义设计层级、开发、测试、评估、审查和文档演进方法。 |
| `docs/Technical Design/FEATURE_ARCHITECTURE_STANDARD.md` | Feature Architecture Standard（功能架构标准） | 定义功能架构的职责、边界、模块地图、主链路和非目标深度。 |
| `docs/Technical Design/MODULE_CONTRACT_STANDARD.md` | Module Contract Standard（模块契约标准） | 定义模块输入、输出、前置条件、失败、验证和不变量。 |
| `docs/Technical Design/Natural Language Query/ARCHITECTURE.md` | Feature Architecture（功能架构） | 定义自然语言查询功能的模块边界、在线/离线链路和外部能力边界。 |
| `docs/Technical Design/Platform Integration/Platform Integration SPEC.md` | Integration Spec（集成规格） | Platform 与 ChatBI 的集成语义；明确 TypeSpec/OpenAPI 事实源关系。 |
| Platform Integration `main.tsp/models.tsp/operations.tsp` | API Contract（API 契约） | TypeSpec 正式机器契约源。 |
| `docs/Technical Design/Platform Integration/generated/openapi.2026-08-12.yaml` | Generated API Documentation（生成接口文档） | TypeSpec 生成的 OpenAPI 3.2 交换产物，不是手工事实源。 |
| `docs/current_project_map.md` | Project Specification Map（项目规格地图） | 当前资产、链路、能力和未确认项；本轮 Semantic Layer V1 重建后已更新关键事实。 |

未发现 README、CHANGELOG、具体 Feature Spec（功能规格）、具体 Module Spec（模块规格）或正式 Evaluation Report（评估报告）。

## 17. Current Capability Matrix（当前能力矩阵）

状态只使用 `Exists（存在）`、`Partial（部分存在）`、`Not Found（未发现）`、`Unclear（无法确认）`。

| 能力 | 状态 | 主要文件 | 当前事实 |
|---|---|---|---|
| Course Baseline PostgreSQL | Exists | `database/course_baseline/`、`scripts/course_baseline/init_database.py` | 五表 SQL、生成器、校验脚本存在；Schema 元数据生成已验证，当前行数未作为本轮事实。 |
| Sales Mart V1 PostgreSQL | Exists | `database/sales_mart/001_create_schema.sql`、`scripts/sales_mart/seed.py`、`tests/sales_mart/test_schema.py` | `mart_sales` 七表、SCD2、销售事实约束和必要索引已实现；15 项结构测试通过，Demo Data 已按 seed=42 加载并通过业务校验。 |
| Schema Catalog | Exists | `resources/schema/{tables,columns,relationships}.json`、`scripts/metadata/export_schema.py` | 当前三份资源是 PostgreSQL `mart_sales` 的 7 表/69 字段/物理约束投影；Course Baseline Metadata 已是遗留资产。 |
| Sales Semantic Layer V1 | Exists | `resources/semantic/sales/metrics.json`、`tests/semantic/test_sales_semantic_resources.py` | 5 个核心指标及其物理映射/依赖契约存在；业务 Dimension 保留在 Domain / Analytical Model，并通过 Column / Field Matching 解析；确定性契约测试通过。 |
| Metric Loader | Not Found | 未发现 | 旧 Loader 已移除；当前 Offline Pipeline V1 模块尚未实现。 |
| Table/Column Loader | Not Found | 未发现 | 旧 Document 加载器已移除；当前 Offline Pipeline V1 模块尚未实现。 |
| BGE-M3 本地 Embedding | Partial / Legacy | `models/bge-m3/` | 本地模型资产保留，但旧 Embedding 适配器已移除；当前无代码消费者。 |
| Qdrant 离线索引 | Partial / Legacy | `data/qdrant/` | 历史持久化目录保留，但旧存储/索引代码已移除；不代表当前索引能力。 |
| Offline Indexing | Not Found | 未发现 | 旧离线索引入口已移除；当前 Offline Pipeline V1 模块尚未实现。 |
| Table Retrieval | Not Found | 未发现 | 没有当前在线 Retriever 或结果契约。 |
| Metric Retrieval | Not Found | 未发现 | 没有当前在线 Retriever；历史持久化资产不代表检索能力。 |
| Schema Linking | Partial | Schema 资源/索引、`relationships.json`、Offline Pipeline Contract | 当前物理目录和 Table / Column / Metric 资产契约存在；没有 Anchor、字段匹配、图搜索或 Join Resolver 运行时实现。 |
| Natural Language Query | Architecture Only（仅有架构） | `docs/Technical Design/Natural Language Query/ARCHITECTURE.md` | 功能架构存在；没有用户问题入口和查询编排。 |
| SQL Generation | Not Found | 未发现 | 没有 LLM Client、Prompt Builder 或 SQL Generator。 |
| SQL AST Validation | Not Found | 未发现 | 没有 SQL AST（抽象语法树）校验模块。 |
| SQL Guard | Not Found | 未发现 | 没有 SELECT-only、白名单、LIMIT 或安全执行器。 |
| Database Execution | Partial | `psycopg` 数据库脚本 | 存在建库/写入/校验连接；没有在线只读查询 Adapter（适配器）。 |
| Business Analysis | Not Found | 仅产品/业务文档 | 文档定义目标，代码未发现实现。 |
| Conversation State | Partial | TypeSpec `StateReference`、SPEC | API 契约描述状态引用；没有 State Store 或运行时状态。 |
| Authentication | Partial | TypeSpec `@useAuth(BearerAuth)`、`PrincipalContext` | 契约存在；没有 API 服务或实际认证处理。 |
| Domain Authorization | Partial | 业务/集成文档、`PrincipalContext` | 语义边界存在；没有确定性授权实现。 |
| Streaming | Partial | TypeSpec SSE、OpenAPI 3.2 | 契约存在；没有流式服务实现，Terminal Model Payload 生成有限制。 |
| Evaluation | Partial | SQL/CLI 校验脚本 | 有数据库和离线索引校验；没有标准测试/评估数据集。 |
| API Contract | Exists | TypeSpec + generated OpenAPI | 正式契约和生成产物存在。 |
| Online API Service | Not Found | 未发现 | 没有 FastAPI 或其他 HTTP Server。 |
| CI/CD | Not Found | `.github/` 不存在 | 未发现自动化流水线。 |
| Deployment | Partial | `docker-compose.yml` | 本地 PostgreSQL/Qdrant 配置存在；没有完整部署资产。 |

## 18. Sources of Truth（事实源）

根据当前文件中的明确声明和代码关系：

- 产品目标：`docs/Business/PRODUCT.md`。
- 销售业务事实、规则和业务意义：`docs/Business/Business Domain.md`；文档自身将 `SALES_DOMAIN.md` 作为命名示例，但该文件未发现。
- 当前销售语义事实：`resources/semantic/sales/metrics.json`；Customer、Product、Time、Region 等业务 Dimension 保留在 DOMAIN_SPEC / ANALYTICAL_MODEL，不建立独立 `dimensions.json`；`tests/semantic/test_sales_semantic_resources.py` 验证当前 Metric Contract 与 Column Metadata 映射。旧 `MetricLoader` 只代表遗留离线输入契约，不反向定义当前业务语义。
- 课程基线物理数据库结构：`database/course_baseline/001_create_tables.sql` 与 PostgreSQL 实际元数据读取逻辑共同出现。
- Sales Mart V1 物理数据库结构：`database/sales_mart/001_create_schema.sql`；`tests/sales_mart/test_schema.py` 是其可重复数据库结构验证入口。
- Schema Metadata（结构元数据）目录：`resources/schema/tables.json`、`columns.json`、`relationships.json`；三份资源由 `scripts/metadata/export_schema.py` 从 PostgreSQL `mart_sales` 一次提取、多份投影，`relationships.json` 只保存物理约束和独立唯一索引。
- 系统架构：`docs/Technical Design/ARCHITECTURE.md`。
- 架构决策：`docs/Technical Design/ARCHITECTURE_DECISIONS.md`。
- 工程方法：`docs/Technical Design/ENGINEERING.md`。
- 功能架构标准：`docs/Technical Design/FEATURE_ARCHITECTURE_STANDARD.md`。
- 模块契约标准：`docs/Technical Design/MODULE_CONTRACT_STANDARD.md`。
- 自然语言查询功能架构：`docs/Technical Design/Natural Language Query/ARCHITECTURE.md`。
- 平台集成语义：`docs/Technical Design/Platform Integration/Platform Integration SPEC.md`。
- 平台正式 API 契约：`main.tsp`、`models.tsp`、`operations.tsp`。
- OpenAPI：`docs/Technical Design/Platform Integration/generated/openapi.2026-08-12.yaml`，属于 Derived Artifact（派生产物）。
- Qdrant 三个 Collection：属于由 JSON/Document/模型构建的派生索引，不是业务事实源。

## 19. Generated Artifacts（生成产物）

已发现的派生或运行时产物：

- `resources/schema/tables.json`
- `resources/schema/columns.json`
- `resources/schema/relationships.json`（PostgreSQL `mart_sales` 物理约束；不包含 `semantic_relationships`）
- `docs/Technical Design/Platform Integration/generated/openapi.2026-08-12.yaml`
- `data/qdrant/collections/*` 向量索引持久化目录
- `scripts/**/__pycache__/`、`tests/**/__pycache__/`、`src/**/__pycache__/`
- `.uv-cache/`、`.model-cache/`、`models/bge-m3/.cache/`
- Platform Integration `node_modules/`

`.gitignore` 已忽略 `.env`、Python/uv 缓存、Node 依赖、数据库数据、Qdrant 数据、BGE-M3 模型和备份目录；`.idea/` 属于本地 IDE 配置，不纳入项目功能资产。

## 20. Uncertainties（未确认项）

1. Docker 容器生命周期状态未独立确认；本轮对 PostgreSQL `mart_sales` Schema Metadata 仅保持只读依赖，并完成 Sales Semantic Layer V1 资源验证，没有重建 Qdrant 或 Retrieval 索引。
2. 当前 `data/postgres` 中存在 PGDATA 和 `postmaster.pid`，但不能据此判断 PostgreSQL 进程正在运行。
3. `chatbi_app` Schema 生成连接和只读权限静态检查已通过；实际业务行数和容器生命周期状态未作为独立审计对象。
4. Qdrant 三个 Collection 的 Point 数量和代表性向量查询已验证；完整服务端配置和持久化一致性未独立审计。
5. `uv.lock` 已锁定 117 个包，`.venv` 已由 `uv sync` 安装；锁定解析依赖网络源，具体供应商包版本随锁文件固定。
6. `.env` 中的 `LLM_*`、`RAG_*`、Qdrant API Key 等配置名存在，但没有对应代码消费者的确认依据。
7. 当前 `resources/schema/relationships.json` 只包含 PostgreSQL `mart_sales` 物理 PK/UNIQUE/FK 和独立唯一索引；没有在线 Relationship Graph（关系图）或 Join Resolver（连接解析器）实现。Sales Semantic Layer V1 不复制 FK 目录；旧 Retrieval Loader 与当前 COMMENT-derived description 及新 Semantic Contract 的兼容性留待后续单独设计。
8. TypeSpec/OpenAPI 生成物存在 Model Terminal Event payload 的已记录保真度限制；下游是否依赖完整的 Terminal Event Schema 未确认。
9. `.jbeval/datasets/` 为空，未发现可复现的 Retrieval/SQL/LLM Evaluation Dataset（评估数据集）。

## Audit Summary（审计总结）

- 当前项目主要由 Course Baseline 与 Sales Mart V1 PostgreSQL 脚本、当前 Sales Semantic Layer V1、Schema Metadata、既有本地 BGE-M3 + Qdrant 离线索引、TypeSpec/OpenAPI 平台契约和说明文档组成。
- 当前已经具备课程数据库基线初始化/生成/校验、Sales Mart V1 七表结构测试、Sales Mart 当前 Schema Metadata 导出/验证、Sales Semantic Layer V1 确定性契约测试、只读权限脚本、既有 Schema/Metric Document Loader、Dense/Sparse 离线向量索引、Qdrant 持久化目录和 OpenAPI 3.2 契约生成能力；本次没有重建后四项 Retrieval/Embedding 资产。
- 当前明显缺少在线 API、用户问题入口、在线 Table/Column/Metric Retrieval、Schema Linking、Join Resolver、LLM 调用、SQL 生成、SQL Guard、在线只读执行、结果格式化、标准测试/评估、CI/CD 和完整部署体系。
- 无法确认的重点是容器/数据库/Qdrant 当前运行状态与实际数据、Python 依赖的真实安装来源、旧 Retrieval Loader 对当前 Schema Metadata 与 Semantic Contract 的后续适配方式、部分文档路径一致性以及下游是否依赖完整 Terminal Event Schema。
