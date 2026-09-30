from scripts.check_module_boundaries import imported_modules, violations


def test_streamlit_allows_standard_library_http_client() -> None:
    imports = imported_modules(
        "from urllib.request import Request, urlopen\nimport json\n"
    )

    assert violations("src/streamlit_app.py", imports) == []


def test_streamlit_rejects_direct_query_runtime_or_database_dependency() -> None:
    imports = imported_modules(
        "from src.online_query.service import OnlineQueryService\nimport sqlalchemy\n"
    )

    errors = violations("src/streamlit_app.py", imports)

    assert len(errors) == 2
    assert all("src/streamlit_app.py" in error for error in errors)
    assert any("src.online_query.service" in error for error in errors)
    assert any("sqlalchemy" in error for error in errors)


def test_query_api_adapter_rejects_concrete_llm_and_executor() -> None:
    imports = imported_modules(
        "from src.online_query.llm import LangChainSQLGenerator\n"
        "from src.online_query.database import PsycopgQueryExecutor\n"
    )

    errors = violations("src/query_api/app.py", imports)

    assert len(errors) == 2
    assert all("src/query_api/app.py" in error for error in errors)


def test_query_api_adapter_rejects_import_from_runtime_package() -> None:
    imports = imported_modules("from src.online_query import llm\n")

    errors = violations("src/query_api/app.py", imports)

    assert len(errors) == 1
    assert "src.online_query.llm" in errors[0]


def test_query_api_composition_root_remains_allowed_to_assemble_adapters() -> None:
    imports = imported_modules(
        "from src.online_query.llm import LangChainSQLGenerator\n"
        "from src.online_query.database import PsycopgQueryExecutor\n"
    )

    assert violations("src/query_api/main.py", imports) == []


def test_rag_offline_rejects_online_and_postgres_dependencies() -> None:
    imports = imported_modules(
        "from src.query_api.app import create_app\nimport psycopg\n"
    )

    errors = violations("src/rag_offline/build.py", imports)

    assert len(errors) == 2
    assert all("src/rag_offline/build.py" in error for error in errors)
