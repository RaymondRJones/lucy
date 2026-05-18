#!/usr/bin/env node

import { execFileSync, spawn } from "node:child_process";
import net from "node:net";
import os from "node:os";

const DEFAULT_WEB_PORT = 3000;
const DEFAULT_API_PORT = 8000;
const DEFAULT_HOST = "0.0.0.0";

function printHelp() {
  console.log(`Run the Lucy app on your local Wi-Fi/LAN.

Usage:
  npm run dev:lan
  npm run dev:lan -- --host 192.168.1.23
  npm run dev:lan -- --name your-computer.local
  npm run dev:lan -- --web-port 3001 --api-port 8001

Environment overrides:
  LAN_HOST          LAN IP address to share with other devices
  LAN_SHARE_HOST    Friendly hostname to print/share, for example your-computer.local
  LAN_WEB_PORT      Web port, default ${DEFAULT_WEB_PORT}
  LAN_API_PORT      API port, default ${DEFAULT_API_PORT}

This exposes the local app and case data to devices that can reach your machine on the same network.
`);
}

function argValue(flag, fallback) {
  const index = process.argv.indexOf(flag);
  if (index !== -1 && process.argv[index + 1]) {
    return process.argv[index + 1];
  }
  return fallback;
}

function detectLanAddress() {
  const interfaces = os.networkInterfaces();
  const candidates = [];
  for (const [name, addresses] of Object.entries(interfaces)) {
    for (const address of addresses ?? []) {
      if (address.family !== "IPv4" || address.internal) {
        continue;
      }
      candidates.push({ name, address: address.address });
    }
  }

  const preferred = candidates.find(({ name }) => /^(en|wl|wifi|wi-fi)/i.test(name));
  return (preferred ?? candidates[0])?.address ?? null;
}

function normalizeLocalName(value) {
  const rawName = String(value ?? "").trim();
  if (!rawName) {
    return null;
  }
  const name = rawName.endsWith(".local") ? rawName : `${rawName}.local`;
  return /^[A-Za-z0-9.-]+$/.test(name) ? name : null;
}

function detectLocalName() {
  try {
    return normalizeLocalName(execFileSync("scutil", ["--get", "LocalHostName"], { encoding: "utf8" }));
  } catch {
    return normalizeLocalName(os.hostname().split(".")[0]);
  }
}

function parsePort(raw, fallback) {
  const value = Number(raw ?? fallback);
  if (!Number.isInteger(value) || value <= 0 || value > 65535) {
    throw new Error(`Invalid port: ${raw}`);
  }
  return value;
}

function canListen(port) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.once("error", () => resolve(false));
    server.once("listening", () => {
      server.close(() => resolve(true));
    });
    server.listen(port, DEFAULT_HOST);
  });
}

function prefixStream(stream, label) {
  let buffered = "";
  stream.setEncoding("utf8");
  stream.on("data", (chunk) => {
    buffered += chunk;
    const lines = buffered.split(/\r?\n/);
    buffered = lines.pop() ?? "";
    for (const line of lines) {
      if (line.trim()) {
        console.log(`[${label}] ${line}`);
      }
    }
  });
  stream.on("end", () => {
    if (buffered.trim()) {
      console.log(`[${label}] ${buffered}`);
    }
  });
}

function startProcess(label, command, args, env) {
  const child = spawn(command, args, {
    env,
    stdio: ["inherit", "pipe", "pipe"],
  });
  prefixStream(child.stdout, label);
  prefixStream(child.stderr, label);
  child.on("exit", (code, signal) => {
    if (signal) {
      console.log(`[${label}] stopped by ${signal}`);
      return;
    }
    if (code !== 0) {
      console.error(`[${label}] exited with code ${code}`);
    }
  });
  return child;
}

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  printHelp();
  process.exit(0);
}

const lanHost = argValue("--host", process.env.LAN_HOST ?? detectLanAddress());
if (!lanHost) {
  console.error("Could not detect a LAN IPv4 address. Re-run with --host <your-lan-ip>.");
  process.exit(1);
}

const webPort = parsePort(argValue("--web-port", process.env.LAN_WEB_PORT), DEFAULT_WEB_PORT);
const apiPort = parsePort(argValue("--api-port", process.env.LAN_API_PORT), DEFAULT_API_PORT);
const shareHost = argValue("--name", process.env.LAN_SHARE_HOST ?? detectLocalName()) ?? lanHost;
const webUrl = `http://${lanHost}:${webPort}`;
const friendlyWebUrl = `http://${shareHost}:${webPort}`;
const friendlyApiUrl = `http://${shareHost}:${apiPort}`;
const corsOrigins = [
  webUrl,
  friendlyWebUrl,
  `http://localhost:${webPort}`,
  `http://127.0.0.1:${webPort}`,
];

if (!(await canListen(webPort))) {
  console.error(`Port ${webPort} is already in use. Stop the web server or pass --web-port <port>.`);
  process.exit(1);
}
if (!(await canListen(apiPort))) {
  console.error(`Port ${apiPort} is already in use. Stop the API server or pass --api-port <port>.`);
  process.exit(1);
}

console.log(`LAN mode starting.

Share this URL with people on your Wi-Fi:
  ${friendlyWebUrl}

Numeric fallback:
  ${webUrl}

API URL:
  ${friendlyApiUrl}

Heads up: anyone who can reach ${friendlyWebUrl} or ${webUrl} while this is running may be able to view or edit local case data.
Press Ctrl+C to stop broadcasting.
`);

const apiEnv = {
  ...process.env,
  GREEN_CARD_PACKET_CORS_ORIGINS: JSON.stringify(corsOrigins),
};
const webEnv = {
  ...process.env,
  NEXT_PUBLIC_API_BASE_URL: "__LAN__",
  NEXT_PUBLIC_API_PORT: String(apiPort),
};

const children = [
  startProcess("api", "./.venv313/bin/uvicorn", [
    "app.main:app",
    "--reload",
    "--app-dir",
    "apps/api",
    "--host",
    DEFAULT_HOST,
    "--port",
    String(apiPort),
  ], apiEnv),
  startProcess("web", "npm", [
    "run",
    "dev",
    "--workspace",
    "web",
    "--",
    "--hostname",
    DEFAULT_HOST,
    "--port",
    String(webPort),
  ], webEnv),
];

function stopChildren(signal) {
  for (const child of children) {
    if (!child.killed) {
      child.kill(signal);
    }
  }
}

process.on("SIGINT", () => {
  stopChildren("SIGINT");
  process.exit(130);
});
process.on("SIGTERM", () => {
  stopChildren("SIGTERM");
  process.exit(143);
});
