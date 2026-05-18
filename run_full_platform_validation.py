import asyncio
import os
import sys
import time
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

async def check_backend(client):
    try:
        t0 = time.monotonic()
        r = await client.get("http://localhost:8000/health", timeout=3.0)
        ms = (time.monotonic() - t0) * 1000
        return True, f"OK ({ms:.0f}ms)", "green"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"

async def check_frontend(client):
    try:
        r = await client.get("http://localhost:5173", timeout=3.0)
        return True, "OK", "green"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"

async def check_ollama(client):
    try:
        r = await client.get("http://localhost:11434/api/tags", timeout=3.0)
        return True, "OK", "green"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"

async def check_worker():
    # Ping backend worker status endpoint
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8000/api/admin/runtime", timeout=3.0)
            if r.status_code == 200:
                data = r.json()
                worker_status = data.get("worker", "unknown")
                if worker_status == "ACTIVE":
                    return True, "Active", "green"
                return False, f"Inactive ({worker_status})", "red"
            return False, f"HTTP {r.status_code}", "red"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"

async def check_websocket():
    import websockets
    try:
        async with websockets.connect("ws://localhost:8000/ws/chat/test-session", close_timeout=2) as ws:
            return True, "Connected", "green"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"

async def check_chroma():
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://localhost:8000/api/admin/runtime", timeout=3.0)
            if r.status_code == 200:
                data = r.json()
                vdb_status = data.get("vectorstore", "unknown")
                if vdb_status == "READY":
                    return True, "Active", "green"
                return False, f"Inactive ({vdb_status})", "red"
            return False, "Failed", "red"
    except Exception as e:
        return False, f"Failed: {type(e).__name__}", "red"


async def run_validation():
    console.print(Panel("[bold cyan]TiO Enterprise Platform Validation Suite[/bold cyan]\nVerifying system integrity...", border_style="cyan"))
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Subsystem", style="dim", width=25)
    table.add_column("Status", width=30)
    table.add_column("Result", justify="center")

    checks = []
    async with httpx.AsyncClient() as client:
        # Core Infrastructure
        backend_ok, backend_msg, backend_color = await check_backend(client)
        table.add_row("Backend (FastAPI)", f"[{backend_color}]{backend_msg}[/{backend_color}]", "PASS" if backend_ok else "FAIL")
        
        frontend_ok, frontend_msg, frontend_color = await check_frontend(client)
        table.add_row("Frontend (Vite/React)", f"[{frontend_color}]{frontend_msg}[/{frontend_color}]", "PASS" if frontend_ok else "FAIL")
        
        ws_ok, ws_msg, ws_color = await check_websocket()
        table.add_row("WebSocket Subsystem", f"[{ws_color}]{ws_msg}[/{ws_color}]", "PASS" if ws_ok else "FAIL")
        
        worker_ok, worker_msg, worker_color = await check_worker()
        table.add_row("Async Worker", f"[{worker_color}]{worker_msg}[/{worker_color}]", "PASS" if worker_ok else "FAIL")
        
        # Intelligence Layer
        ollama_ok, ollama_msg, ollama_color = await check_ollama(client)
        table.add_row("LLM Engine (Ollama)", f"[{ollama_color}]{ollama_msg}[/{ollama_color}]", "PASS" if ollama_ok else "FAIL")
        
        vdb_ok, vdb_msg, vdb_color = await check_chroma()
        table.add_row("Vectorstore (ChromaDB)", f"[{vdb_color}]{vdb_msg}[/{vdb_color}]", "PASS" if vdb_ok else "FAIL")

    console.print(table)
    
    if all([backend_ok, frontend_ok, ws_ok, worker_ok, ollama_ok, vdb_ok]):
        console.print(Panel("[bold green]All systems nominal. TiO is deployment-ready.[/bold green]", border_style="green"))
    else:
        console.print(Panel("[bold red]CRITICAL: Some subsystems failed validation. Check logs.[/bold red]", border_style="red"))

if __name__ == "__main__":
    try:
        asyncio.run(run_validation())
    except KeyboardInterrupt:
        console.print("\n[yellow]Validation aborted.[/yellow]")
