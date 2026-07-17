import inspect
import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

from glide import GlideClient, RequestError
from glide.async_commands import ft

from cocoindex.connectors import valkey
import main


def test_index_name_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("COCOINDEX_INDEX_NAME", "isolated_rag_documents")

    assert main.get_index_name() == "isolated_rag_documents"


def test_result_count_label_reports_returned_rows() -> None:
    assert main.format_result_count(5) == "Returned results: 5"


def test_build_knn_query_uses_a_bound_vector_parameter() -> None:
    query = main.build_knn_query(top_k=3, filter_filename="valkey.md")

    assert query == "@filename:{valkey.md}=>[KNN 3 @vector $query_vec AS score]"


def test_default_hybrid_filter_matches_the_fixture_path() -> None:
    query = main.build_knn_query(top_k=5, filter_filename=main.DEFAULT_FILTER_FILENAME)

    assert query == (
        "@filename:{markdown_files/valkey.md}=>"
        "[KNN 5 @vector $query_vec AS score]"
    )


def test_verify_is_async() -> None:
    assert inspect.iscoroutinefunction(main.verify)


def test_cocoindex_update_creates_searchable_fixture_index(tmp_path: Path) -> None:
    sample_dir = Path(__file__).parent
    env = os.environ.copy()
    env["COCOINDEX_DB"] = str(tmp_path / "cocoindex.db")
    index_name = f"rag_documents_test_{uuid.uuid4().hex}"
    env["COCOINDEX_INDEX_NAME"] = index_name
    previous_index_name = os.environ.get("COCOINDEX_INDEX_NAME")
    os.environ["COCOINDEX_INDEX_NAME"] = index_name

    try:
        asyncio.run(cleanup_valkey(index_name))
        subprocess.run(
            [
                str(Path(sys.executable).with_name("cocoindex")),
                "update",
                "--reset",
                "-f",
                "main",
            ],
            cwd=sample_dir,
            env=env,
            check=True,
        )
        results = asyncio.run(main.verify("open source in-memory database"))
        assert any("valkey.md" in result["filename"] for result in results)
        index_names = asyncio.run(list_indexes())
        assert index_name in index_names
    finally:
        asyncio.run(cleanup_valkey(index_name))
        if previous_index_name is None:
            os.environ.pop("COCOINDEX_INDEX_NAME", None)
        else:
            os.environ["COCOINDEX_INDEX_NAME"] = previous_index_name


async def list_indexes() -> set[str]:
    client = await GlideClient.create(
        valkey.create_client_config(main.VALKEY_HOST, main.VALKEY_PORT)
    )
    try:
        names = await ft.list(client)
        return {
            name.decode() if isinstance(name, bytes) else str(name) for name in names
        }
    finally:
        await client.close()


async def cleanup_valkey(index_name: str) -> None:
    client = await GlideClient.create(
        valkey.create_client_config(main.VALKEY_HOST, main.VALKEY_PORT)
    )
    try:
        try:
            await ft.dropindex(client, index_name)
        except RequestError:
            pass

        cursor: str | int = "0"
        while True:
            response = await client.scan(
                cursor,
                match=f"{index_name}:*",
                count=500,
            )
            cursor, keys = response
            if keys:
                await client.delete(keys)
            if cursor in ("0", 0, b"0"):
                break
    finally:
        await client.close()
