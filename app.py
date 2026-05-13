#!/usr/bin/env python3
"""
Single-file Snake game web service.

Run:
    python app.py

Environment:
    HOST=0.0.0.0
    PORT=8000
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


APP_NAME = os.getenv("APP_NAME", "Snake Game")
APP_VERSION = os.getenv("APP_VERSION", "2.0.0")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
START_TIME = time.time()


def iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def uptime_seconds() -> int:
    return int(time.time() - START_TIME)


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class AppHandler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/{APP_VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stdout.write(
            json.dumps(
                {
                    "time": iso_now(),
                    "client": self.client_address[0],
                    "method": self.command,
                    "path": self.path,
                    "message": fmt % args,
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def do_GET(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/":
                self.send_html(render_home())
            elif path == "/healthz":
                self.send_json({"status": "ok", "time": iso_now(), "uptime_seconds": uptime_seconds()})
            elif path == "/api/status":
                self.send_json(
                    {
                        "app": APP_NAME,
                        "version": APP_VERSION,
                        "status": "ok",
                        "time": iso_now(),
                        "uptime_seconds": uptime_seconds(),
                        "hostname": socket.gethostname(),
                    }
                )
            else:
                self.send_json({"error": "not_found", "path": path}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_exception(exc)

    def handle_exception(self, exc: Exception) -> None:
        traceback.print_exc()
        self.send_json(
            {"error": "internal_error", "message": str(exc), "time": iso_now()},
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def render_home() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Snake Game</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #12151f;
      --surface: #1b2030;
      --surface-2: #242b3d;
      --line: #343d53;
      --text: #f4f7fb;
      --muted: #aeb8c8;
      --snake: #42d68c;
      --snake-head: #8cf2ba;
      --food: #ff5c7a;
      --gold: #ffd166;
      --blue: #63c7ff;
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 22px;
      background:
        radial-gradient(circle at 20% 10%, rgba(99, 199, 255, .16), transparent 32%),
        radial-gradient(circle at 88% 90%, rgba(66, 214, 140, .16), transparent 30%),
        var(--bg);
      color: var(--text);
      font-family: Arial, "Microsoft YaHei", sans-serif;
    }

    main {
      width: min(1100px, 100%);
      display: grid;
      grid-template-columns: minmax(320px, 680px) minmax(260px, 340px);
      gap: 18px;
      align-items: start;
    }

    .game-panel,
    .side-panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(27, 32, 48, .92);
      box-shadow: 0 22px 70px rgba(0, 0, 0, .35);
    }

    .game-panel {
      padding: clamp(14px, 3vw, 24px);
    }

    .topbar {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: center;
      margin-bottom: 16px;
    }

    h1 {
      margin: 0;
      font-size: clamp(26px, 4vw, 44px);
      letter-spacing: 0;
      line-height: 1;
    }

    .status {
      color: var(--muted);
      margin-top: 8px;
      font-size: 14px;
    }

    .score-box {
      min-width: 112px;
      padding: 10px 12px;
      border-radius: 8px;
      border: 1px solid var(--line);
      background: var(--surface-2);
      text-align: right;
    }

    .score-box span {
      display: block;
      color: var(--muted);
      font-size: 12px;
    }

    .score-box strong {
      display: block;
      margin-top: 4px;
      font-size: 28px;
      color: var(--gold);
    }

    .board-wrap {
      position: relative;
      width: 100%;
      aspect-ratio: 1 / 1;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--line);
      background: #0e121a;
    }

    canvas {
      width: 100%;
      height: 100%;
      display: block;
    }

    .overlay {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 20px;
      background: rgba(8, 10, 15, .68);
      text-align: center;
    }

    .overlay.hidden {
      display: none;
    }

    .overlay-box {
      width: min(360px, 100%);
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(27, 32, 48, .96);
    }

    .overlay-title {
      margin: 0 0 10px;
      font-size: 28px;
    }

    .overlay-text {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.6;
    }

    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }

    button {
      min-height: 42px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0 14px;
      background: var(--surface-2);
      color: var(--text);
      font: inherit;
      cursor: pointer;
    }

    button.primary {
      border: 0;
      background: linear-gradient(135deg, var(--snake), var(--blue));
      color: #081018;
      font-weight: 700;
    }

    button:focus-visible {
      outline: 3px solid rgba(99, 199, 255, .4);
      outline-offset: 2px;
    }

    .side-panel {
      padding: 18px;
    }

    .stat-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-bottom: 18px;
    }

    .stat {
      min-height: 76px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface-2);
    }

    .stat span {
      display: block;
      color: var(--muted);
      font-size: 12px;
    }

    .stat strong {
      display: block;
      margin-top: 8px;
      font-size: 22px;
    }

    .control-pad {
      display: grid;
      grid-template-columns: repeat(3, 56px);
      gap: 8px;
      justify-content: center;
      margin: 18px 0;
    }

    .control-pad button {
      width: 56px;
      height: 52px;
      padding: 0;
      font-size: 22px;
      font-weight: 700;
    }

    .control-pad .up {
      grid-column: 2;
    }

    .control-pad .left {
      grid-column: 1;
    }

    .control-pad .down {
      grid-column: 2;
    }

    .control-pad .right {
      grid-column: 3;
    }

    .tips {
      margin: 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      line-height: 1.8;
      font-size: 14px;
    }

    .tips strong {
      color: var(--text);
    }

    @media (max-width: 850px) {
      body {
        align-items: start;
        padding: 14px;
      }

      main {
        grid-template-columns: 1fr;
      }

      .topbar {
        align-items: flex-start;
      }
    }

    @media (max-width: 460px) {
      .topbar {
        flex-direction: column;
      }

      .score-box {
        width: 100%;
        text-align: left;
      }

      .actions {
        display: grid;
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="game-panel">
      <div class="topbar">
        <div>
          <h1>贪吃蛇</h1>
          <div class="status" id="statusText">按开始，吃到红色食物就加分。</div>
        </div>
        <div class="score-box">
          <span>当前分数</span>
          <strong id="score">0</strong>
        </div>
      </div>

      <div class="board-wrap">
        <canvas id="board" width="600" height="600"></canvas>
        <div class="overlay" id="overlay">
          <div class="overlay-box">
            <h2 class="overlay-title" id="overlayTitle">准备开始</h2>
            <p class="overlay-text" id="overlayText">方向键或下方按钮控制方向，不要撞墙，也不要咬到自己。</p>
            <div class="actions">
              <button class="primary" id="startBtn">开始游戏</button>
              <button id="resetBtn">重新开始</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <aside class="side-panel">
      <div class="stat-grid">
        <div class="stat">
          <span>最高分</span>
          <strong id="bestScore">0</strong>
        </div>
        <div class="stat">
          <span>速度</span>
          <strong id="speedText">普通</strong>
        </div>
        <div class="stat">
          <span>蛇身长度</span>
          <strong id="lengthText">3</strong>
        </div>
        <div class="stat">
          <span>状态</span>
          <strong id="stateText">待开始</strong>
        </div>
      </div>

      <div class="actions">
        <button class="primary" id="pauseBtn">暂停</button>
        <button id="slowBtn">慢速</button>
        <button id="normalBtn">普通</button>
        <button id="fastBtn">快速</button>
      </div>

      <div class="control-pad" aria-label="方向控制">
        <button class="up" data-dir="up" aria-label="向上">↑</button>
        <button class="left" data-dir="left" aria-label="向左">←</button>
        <button class="down" data-dir="down" aria-label="向下">↓</button>
        <button class="right" data-dir="right" aria-label="向右">→</button>
      </div>

      <ul class="tips">
        <li><strong>电脑：</strong>用方向键控制。</li>
        <li><strong>手机：</strong>点方向按钮控制。</li>
        <li><strong>目标：</strong>吃红色食物，越长分越高。</li>
      </ul>
    </aside>
  </main>

  <script>
    const canvas = document.getElementById('board');
    const ctx = canvas.getContext('2d');
    const scoreEl = document.getElementById('score');
    const bestScoreEl = document.getElementById('bestScore');
    const speedText = document.getElementById('speedText');
    const lengthText = document.getElementById('lengthText');
    const stateText = document.getElementById('stateText');
    const statusText = document.getElementById('statusText');
    const overlay = document.getElementById('overlay');
    const overlayTitle = document.getElementById('overlayTitle');
    const overlayText = document.getElementById('overlayText');
    const startBtn = document.getElementById('startBtn');
    const resetBtn = document.getElementById('resetBtn');
    const pauseBtn = document.getElementById('pauseBtn');

    const gridSize = 20;
    const tileCount = canvas.width / gridSize;
    const speeds = {
      slow: { label: '慢速', ms: 170 },
      normal: { label: '普通', ms: 125 },
      fast: { label: '快速', ms: 85 }
    };

    let snake;
    let food;
    let direction;
    let nextDirection;
    let score;
    let bestScore = Number(localStorage.getItem('snakeBestScore') || 0);
    let timer = null;
    let running = false;
    let paused = false;
    let speedKey = 'normal';

    function newGame() {
      snake = [
        { x: 10, y: 10 },
        { x: 9, y: 10 },
        { x: 8, y: 10 }
      ];
      direction = { x: 1, y: 0 };
      nextDirection = { x: 1, y: 0 };
      score = 0;
      paused = false;
      placeFood();
      updateInfo('待开始');
      draw();
      showOverlay('准备开始', '方向键或下方按钮控制方向，不要撞墙，也不要咬到自己。');
    }

    function startGame() {
      if (running && !paused) return;
      running = true;
      paused = false;
      hideOverlay();
      updateInfo('进行中');
      restartTimer();
    }

    function restartGame() {
      stopTimer();
      running = false;
      newGame();
      startGame();
    }

    function restartTimer() {
      stopTimer();
      timer = setInterval(step, speeds[speedKey].ms);
    }

    function stopTimer() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    function togglePause() {
      if (!running) return;
      paused = !paused;
      if (paused) {
        stopTimer();
        updateInfo('已暂停');
        showOverlay('已暂停', '点继续游戏，或者按空格恢复。');
        startBtn.textContent = '继续游戏';
      } else {
        hideOverlay();
        updateInfo('进行中');
        restartTimer();
      }
    }

    function step() {
      direction = nextDirection;
      const head = snake[0];
      const nextHead = { x: head.x + direction.x, y: head.y + direction.y };

      if (hitWall(nextHead) || hitSelf(nextHead)) {
        gameOver();
        return;
      }

      snake.unshift(nextHead);
      if (nextHead.x === food.x && nextHead.y === food.y) {
        score += 10;
        placeFood();
      } else {
        snake.pop();
      }

      updateInfo('进行中');
      draw();
    }

    function hitWall(part) {
      return part.x < 0 || part.x >= tileCount || part.y < 0 || part.y >= tileCount;
    }

    function hitSelf(part) {
      return snake.some(item => item.x === part.x && item.y === part.y);
    }

    function placeFood() {
      do {
        food = {
          x: Math.floor(Math.random() * tileCount),
          y: Math.floor(Math.random() * tileCount)
        };
      } while (snake.some(item => item.x === food.x && item.y === food.y));
    }

    function gameOver() {
      stopTimer();
      running = false;
      paused = false;
      if (score > bestScore) {
        bestScore = score;
        localStorage.setItem('snakeBestScore', String(bestScore));
      }
      updateInfo('游戏结束');
      draw();
      showOverlay('游戏结束', `本次得分 ${score}。点重新开始再来一局。`);
      startBtn.textContent = '开始游戏';
    }

    function setDirection(name) {
      const map = {
        up: { x: 0, y: -1 },
        down: { x: 0, y: 1 },
        left: { x: -1, y: 0 },
        right: { x: 1, y: 0 }
      };
      const wanted = map[name];
      if (!wanted) return;
      if (wanted.x + direction.x === 0 && wanted.y + direction.y === 0) return;
      nextDirection = wanted;
      if (!running) startGame();
    }

    function setSpeed(key) {
      speedKey = key;
      speedText.textContent = speeds[speedKey].label;
      if (running && !paused) restartTimer();
    }

    function updateInfo(state) {
      scoreEl.textContent = score;
      bestScoreEl.textContent = bestScore;
      lengthText.textContent = snake.length;
      speedText.textContent = speeds[speedKey].label;
      stateText.textContent = state;
      statusText.textContent = state === '进行中'
        ? '正在游戏，吃到红色食物加 10 分。'
        : '按开始，吃到红色食物就加分。';
      pauseBtn.textContent = paused ? '继续' : '暂停';
    }

    function showOverlay(title, text) {
      overlayTitle.textContent = title;
      overlayText.textContent = text;
      overlay.classList.remove('hidden');
    }

    function hideOverlay() {
      overlay.classList.add('hidden');
      startBtn.textContent = '开始游戏';
    }

    function draw() {
      ctx.fillStyle = '#0e121a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      drawGrid();

      snake.forEach((part, index) => {
        const x = part.x * gridSize;
        const y = part.y * gridSize;
        ctx.fillStyle = index === 0 ? '#8cf2ba' : '#42d68c';
        roundRect(x + 2, y + 2, gridSize - 4, gridSize - 4, 5);
        ctx.fill();
      });

      ctx.fillStyle = '#ff5c7a';
      ctx.beginPath();
      ctx.arc(
        food.x * gridSize + gridSize / 2,
        food.y * gridSize + gridSize / 2,
        gridSize * 0.34,
        0,
        Math.PI * 2
      );
      ctx.fill();
    }

    function drawGrid() {
      ctx.strokeStyle = 'rgba(255, 255, 255, .045)';
      ctx.lineWidth = 1;
      for (let i = 0; i <= tileCount; i += 1) {
        const pos = i * gridSize + 0.5;
        ctx.beginPath();
        ctx.moveTo(pos, 0);
        ctx.lineTo(pos, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, pos);
        ctx.lineTo(canvas.width, pos);
        ctx.stroke();
      }
    }

    function roundRect(x, y, width, height, radius) {
      ctx.beginPath();
      ctx.moveTo(x + radius, y);
      ctx.lineTo(x + width - radius, y);
      ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
      ctx.lineTo(x + width, y + height - radius);
      ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
      ctx.lineTo(x + radius, y + height);
      ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
      ctx.lineTo(x, y + radius);
      ctx.quadraticCurveTo(x, y, x + radius, y);
      ctx.closePath();
    }

    document.addEventListener('keydown', event => {
      const keys = {
        ArrowUp: 'up',
        ArrowDown: 'down',
        ArrowLeft: 'left',
        ArrowRight: 'right'
      };
      if (keys[event.key]) {
        event.preventDefault();
        setDirection(keys[event.key]);
      }
      if (event.code === 'Space') {
        event.preventDefault();
        togglePause();
      }
    });

    document.querySelectorAll('[data-dir]').forEach(button => {
      button.addEventListener('click', () => setDirection(button.dataset.dir));
    });

    startBtn.addEventListener('click', () => {
      if (paused) {
        togglePause();
      } else {
        startGame();
      }
    });
    resetBtn.addEventListener('click', restartGame);
    pauseBtn.addEventListener('click', togglePause);
    document.getElementById('slowBtn').addEventListener('click', () => setSpeed('slow'));
    document.getElementById('normalBtn').addEventListener('click', () => setSpeed('normal'));
    document.getElementById('fastBtn').addEventListener('click', () => setSpeed('fast'));

    newGame();
  </script>
</body>
</html>"""


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(
        json.dumps(
            {
                "time": iso_now(),
                "event": "server_started",
                "app": APP_NAME,
                "version": APP_VERSION,
                "listen": f"http://{HOST}:{PORT}",
                "health": "/healthz",
            },
            ensure_ascii=False,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
