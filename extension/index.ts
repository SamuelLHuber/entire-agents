import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawn, type ChildProcess } from "node:child_process";
import { fileURLToPath } from "node:url";

export default function (pi: ExtensionAPI) {
  let worker: ChildProcess | undefined;
  pi.on("session_start", async (_event, ctx) => {
    const id = ctx.sessionManager.getSessionId();
    const file = ctx.sessionManager.getSessionFile();
    process.env.AGENT_SESSION_ID = id;
    if (!file) throw new Error("Session persistence is required for attribution");
    if (!process.env.AGENT_S3_BUCKET && !process.env.AGENT_SESSION_INGEST_URL) return;
    const configured = process.env.AGENT_SESSION_SYNC_COMMAND;
    const command = configured || "python3";
    const args = configured
      ? [file, id]
      : [fileURLToPath(new URL("../sync.py", import.meta.url)), file, id];
    worker = spawn(command, args, {
      env: process.env, stdio: ["ignore", "ignore", "inherit"],
    });
    worker.on("error", (error) => console.error("session sync unavailable:", error));
  });
  pi.on("session_shutdown", async () => {
    if (worker && worker.exitCode === null) {
      const exited = new Promise<void>((resolve) => worker!.once("exit", () => resolve()));
      worker.kill("SIGTERM");
      await exited;
    }
    worker = undefined;
    delete process.env.AGENT_SESSION_ID;
  });
}
