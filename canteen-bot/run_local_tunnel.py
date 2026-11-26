"""Run the local Mini App and bot through a temporary Serveo SSH tunnel.

Usage from this directory: py run_local_tunnel.py
Keep this terminal open while testing. The generated URL changes on restart.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from pathlib import Path

from aiohttp import web

from web_server import create_app

PROJECT_DIR = Path(__file__).resolve().parent
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.(?:serveousercontent\.com|serveo\.net)", re.IGNORECASE)
LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = int(os.getenv("LOCAL_WEB_PORT", "8084"))


def find_ssh() -> str:
    ssh = shutil.which("ssh")
    if not ssh:
        raise RuntimeError("Не найден ssh.exe. Установите клиент OpenSSH для Windows.")
    return ssh


async def wait_for_tunnel(process: asyncio.subprocess.Process) -> str:
    assert process.stdout is not None
    while True:
        line = await process.stdout.readline()
        if not line:
            code = await process.wait()
            raise RuntimeError(f"SSH-туннель завершился до выдачи ссылки (код {code}).")
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"[ssh-tunnel] {text}")
        match = TUNNEL_URL.search(text)
        if match:
            return match.group(0)


async def print_tunnel_output(process: asyncio.subprocess.Process) -> None:
    assert process.stdout is not None
    async for line in process.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"[ssh-tunnel] {text}")


async def run() -> None:
    tunnel_process = None
    runner = web.AppRunner(create_app())
    try:
        await runner.setup()
        site = web.TCPSite(runner, LOCAL_HOST, LOCAL_PORT)
        await site.start()
        local_url = f"http://{LOCAL_HOST}:{LOCAL_PORT}"
        print(f"Локальное приложение запущено: {local_url}")

        # Serveo's SSH endpoint on 443 avoids Cloudflare's blocked port 7844.
        tunnel_process = await asyncio.create_subprocess_exec(
            find_ssh(), "-p", "443", "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30", "-o", "ServerAliveCountMax=3",
            "-R", f"80:{LOCAL_HOST}:{LOCAL_PORT}", "serveo.net",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        public_url = await asyncio.wait_for(wait_for_tunnel(tunnel_process), timeout=45)

        # Set before importing main: it reads BOT_TOKEN and WEBAPP_URL at import time.
        os.environ["WEBAPP_URL"] = public_url
        os.environ["WEB_HOST"] = LOCAL_HOST
        os.environ["WEB_PORT"] = str(LOCAL_PORT)
        print("\nВременная ссылка для Mini App:")
        print(public_url)
        print("Бот запускается с этой ссылкой через SSH-туннель. Не закрывайте это окно во время проверки.\n")

        output_task = asyncio.create_task(print_tunnel_output(tunnel_process))
        import main as bot_app

        try:
            await bot_app.main(web_server_started=True)
        finally:
            output_task.cancel()
            await asyncio.gather(output_task, return_exceptions=True)
    finally:
        if tunnel_process is not None and tunnel_process.returncode is None:
            tunnel_process.terminate()
            try:
                await asyncio.wait_for(tunnel_process.wait(), timeout=5)
            except asyncio.TimeoutError:
                tunnel_process.kill()
                await tunnel_process.wait()
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nЛокальное приложение и временный туннель остановлены.")
    except Exception as exc:
        print(f"Ошибка локального запуска: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
