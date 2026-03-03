#!/usr/bin/env python3
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests

SOURCE_URL = os.environ.get("SOURCE_URL", "https://supabase.proframos.com")
SOURCE_KEY = os.environ.get("SOURCE_SERVICE_KEY", "")
MCP_URL = os.environ.get("DEST_MCP_URL", "https://mcp.supabase.com/mcp?project_ref=edckgpfzoditeiphilhy")
MCP_TOKEN = os.environ.get("DEST_MCP_TOKEN", "")

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SQL_PATH = ROOT / "docs" / "plans" / "RAG" / "supabase_rag_schema.sql"

REQ_TIMEOUT = 120


def must(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass
class MCPClient:
    url: str
    token: str
    session_id: str | None = None

    def init(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "botsalinha-backup", "version": "1.0"},
            },
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        r = requests.post(self.url, headers=headers, json=payload, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        self.session_id = r.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("MCP session id missing")

    def tool_call(self, name: str, arguments: Dict[str, Any]) -> Any:
        if not self.session_id:
            self.init()
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 2147483647,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers = {
            "Authorization": f"Bearer {self.token}",
            "mcp-session-id": self.session_id,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        r = requests.post(self.url, headers=headers, json=payload, timeout=REQ_TIMEOUT)
        if r.status_code in (401, 403):
            self.session_id = None
            self.init()
            headers["mcp-session-id"] = self.session_id or ""
            r = requests.post(self.url, headers=headers, json=payload, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        return data.get("result", {})

    def execute_sql(self, query: str) -> Any:
        return self.tool_call("execute_sql", {"query": query})

    def apply_migration(self, name: str, query: str) -> Any:
        return self.tool_call("apply_migration", {"name": name, "query": query})


def quote_sql(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value).replace("'", "''")
    return f"'{s}'"


def quote_jsonb(value: Any) -> str:
    if value is None:
        return "'{}'::jsonb"
    s = json.dumps(value, ensure_ascii=False).replace("'", "''")
    return f"'{s}'::jsonb"


def get_source_count(table: str) -> int:
    headers = {
        "apikey": SOURCE_KEY,
        "Authorization": f"Bearer {SOURCE_KEY}",
        "Prefer": "count=exact",
        "Range": "0-0",
    }
    r = requests.get(f"{SOURCE_URL}/rest/v1/{table}?select=id", headers=headers, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    content_range = r.headers.get("Content-Range", "0-0/0")
    return int(content_range.split("/")[-1])


def fetch_rows(table: str, select: str, order: str = "id", page_size: int = 200) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    headers = {"apikey": SOURCE_KEY, "Authorization": f"Bearer {SOURCE_KEY}"}
    offset = 0
    while True:
        params = {
            "select": select,
            "order": f"{order}.asc",
            "limit": str(page_size),
            "offset": str(offset),
        }
        r = requests.get(f"{SOURCE_URL}/rest/v1/{table}", headers=headers, params=params, timeout=REQ_TIMEOUT)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        print(f"[source] {table}: fetched {len(rows)}")
    return rows


def run_with_retry(fn, attempts: int = 4, sleep_s: float = 2.0):
    last = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            print(f"[retry {i}/{attempts}] {e}")
            time.sleep(sleep_s * i)
    raise last  # type: ignore[misc]


def parse_execute_rows(result: Any) -> Any:
    content = result.get("content", []) if isinstance(result, dict) else []
    if not content:
        return None
    text = content[0].get("text")
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def ensure_schema(client: MCPClient) -> None:
    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    run_with_retry(lambda: client.apply_migration("botsalinha_rag_schema_backup", schema_sql))


def truncate_dest(client: MCPClient) -> None:
    q = "truncate table public.content_links, public.rag_chunks, public.rag_documents restart identity cascade;"
    run_with_retry(lambda: client.execute_sql(q))


def insert_documents(client: MCPClient, rows: List[Dict[str, Any]], batch_size: int = 200) -> None:
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        values = []
        for r in batch:
            values.append(
                "("
                + ", ".join(
                    [
                        quote_sql(r.get("id")),
                        quote_sql(r.get("nome")),
                        quote_sql(r.get("arquivo_origem")),
                        quote_sql(r.get("content_hash")),
                        quote_sql(r.get("schema_version") or 1),
                        quote_sql(r.get("chunk_count") or 0),
                        quote_sql(r.get("token_count") or 0),
                        quote_sql(r.get("created_at")),
                    ]
                )
                + ")"
            )
        q = (
            "insert into public.rag_documents "
            "(id,nome,arquivo_origem,content_hash,schema_version,chunk_count,token_count,created_at) values "
            + ",\n".join(values)
            + " on conflict (id) do update set "
            "nome=excluded.nome,arquivo_origem=excluded.arquivo_origem,content_hash=excluded.content_hash,"
            "schema_version=excluded.schema_version,chunk_count=excluded.chunk_count,token_count=excluded.token_count,created_at=excluded.created_at;"
        )
        run_with_retry(lambda: client.execute_sql(q))
        print(f"[dest] rag_documents inserted {min(i + batch_size, len(rows))}/{len(rows)}")


def insert_chunks(client: MCPClient, rows: List[Dict[str, Any]], batch_size: int = 10) -> None:
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        values = []
        for r in batch:
            emb = r.get("embedding")
            emb_sql = "NULL" if emb in (None, "") else f"{quote_sql(emb)}::extensions.vector"
            values.append(
                "("
                + ", ".join(
                    [
                        quote_sql(r.get("id")),
                        quote_sql(r.get("documento_id")),
                        quote_sql(r.get("texto")),
                        quote_jsonb(r.get("metadados") or {}),
                        quote_sql(r.get("content_hash")),
                        quote_sql(r.get("metadata_version") or 1),
                        quote_sql(r.get("token_count") or 0),
                        emb_sql,
                        quote_sql(r.get("created_at")),
                    ]
                )
                + ")"
            )
        q = (
            "insert into public.rag_chunks "
            "(id,documento_id,texto,metadados,content_hash,metadata_version,token_count,embedding,created_at) values "
            + ",\n".join(values)
            + " on conflict (id) do update set "
            "documento_id=excluded.documento_id,texto=excluded.texto,metadados=excluded.metadados,content_hash=excluded.content_hash,"
            "metadata_version=excluded.metadata_version,token_count=excluded.token_count,embedding=excluded.embedding,created_at=excluded.created_at;"
        )
        run_with_retry(lambda: client.execute_sql(q), attempts=5, sleep_s=3)
        print(f"[dest] rag_chunks inserted {min(i + batch_size, len(rows))}/{len(rows)}")


def insert_links(client: MCPClient, rows: List[Dict[str, Any]], batch_size: int = 500) -> None:
    if not rows:
        return
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        values = []
        for r in batch:
            values.append(
                "("
                + ", ".join(
                    [
                        quote_sql(r.get("id")),
                        quote_sql(r.get("article_chunk_id")),
                        quote_sql(r.get("linked_chunk_id")),
                        quote_sql(r.get("link_type")),
                        quote_sql(r.get("created_at")),
                    ]
                )
                + ")"
            )
        q = (
            "insert into public.content_links "
            "(id,article_chunk_id,linked_chunk_id,link_type,created_at) values "
            + ",\n".join(values)
            + " on conflict (id) do update set "
            "article_chunk_id=excluded.article_chunk_id,linked_chunk_id=excluded.linked_chunk_id,link_type=excluded.link_type,created_at=excluded.created_at;"
        )
        run_with_retry(lambda: client.execute_sql(q))
        print(f"[dest] content_links inserted {min(i + batch_size, len(rows))}/{len(rows)}")


def get_dest_counts(client: MCPClient) -> Dict[str, int]:
    q = (
        "select "
        "(select count(*)::int from public.rag_documents) as rag_documents,"
        "(select count(*)::int from public.rag_chunks) as rag_chunks,"
        "(select count(*)::int from public.content_links) as content_links;"
    )
    result = run_with_retry(lambda: client.execute_sql(q))
    parsed = parse_execute_rows(result)
    if isinstance(parsed, list) and parsed:
        return {
            "rag_documents": int(parsed[0]["rag_documents"]),
            "rag_chunks": int(parsed[0]["rag_chunks"]),
            "content_links": int(parsed[0]["content_links"]),
        }
    raise RuntimeError(f"Unexpected result for dest counts: {parsed}")


def main() -> None:
    must("SOURCE_SERVICE_KEY", SOURCE_KEY)
    must("DEST_MCP_TOKEN", MCP_TOKEN)

    print("[1/6] Initializing MCP client")
    client = MCPClient(MCP_URL, MCP_TOKEN)
    client.init()

    print("[2/6] Ensuring destination schema")
    ensure_schema(client)

    print("[3/6] Fetching source counts")
    src_counts = {
        "rag_documents": get_source_count("rag_documents"),
        "rag_chunks": get_source_count("rag_chunks"),
        "content_links": get_source_count("content_links"),
    }
    print(f"[source counts] {src_counts}")

    print("[4/6] Truncating destination tables")
    truncate_dest(client)

    print("[5/6] Copying rows")
    documents = fetch_rows(
        "rag_documents",
        "id,nome,arquivo_origem,content_hash,schema_version,chunk_count,token_count,created_at",
        page_size=500,
    )
    insert_documents(client, documents)

    chunks = fetch_rows(
        "rag_chunks",
        "id,documento_id,texto,metadados,content_hash,metadata_version,token_count,embedding,created_at",
        page_size=100,
    )
    insert_chunks(client, chunks, batch_size=10)

    links = fetch_rows(
        "content_links",
        "id,article_chunk_id,linked_chunk_id,link_type,created_at",
        page_size=500,
    )
    insert_links(client, links)

    print("[6/6] Validating destination counts")
    dest_counts = get_dest_counts(client)
    print(f"[dest counts] {dest_counts}")

    if src_counts != dest_counts:
        raise RuntimeError(f"Count mismatch: source={src_counts} dest={dest_counts}")

    print("Backup A -> B completed successfully.")


if __name__ == "__main__":
    main()
