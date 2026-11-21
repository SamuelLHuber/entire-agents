const vscode = require("vscode");

function configureTerminalEnvironment(context) {
  const collection = context.environmentVariableCollection;
  const config = vscode.workspace.getConfiguration("agentSessionProvenance");
  const configured = String(config.get("sessionId") || "").trim();

  collection.clear();

  // VS Code/Cursor environment collections affect integrated terminals created
  // after activation. They do not prove Cursor Agent workers inherit this env.
  if (configured.length > 0) {
    collection.replace("AGENT_SESSION_ID", configured);
  }

  if (process.env.AGENT_SESSION_SYNC_COMMAND) {
    collection.replace("AGENT_SESSION_SYNC_COMMAND", process.env.AGENT_SESSION_SYNC_COMMAND);
  }
  if (process.env.AGENT_SESSION_INGEST_URL) {
    collection.replace("AGENT_SESSION_INGEST_URL", process.env.AGENT_SESSION_INGEST_URL);
  }
  if (process.env.AGENT_SESSION_INGEST_BEARER_FILE) {
    collection.replace("AGENT_SESSION_INGEST_BEARER_FILE", process.env.AGENT_SESSION_INGEST_BEARER_FILE);
  }
}

async function checkEnvironment() {
  const terminalSession = vscode.workspace.getConfiguration("agentSessionProvenance").get("sessionId") || "";
  const lines = [
    "Agent Session Provenance",
    "",
    `Extension process AGENT_SESSION_ID: ${process.env.AGENT_SESSION_ID || "(unset)"}`,
    `Configured terminal session id: ${terminalSession || "(unset)"}`,
    "",
    "This Cursor extension can seed integrated terminals. Full Cursor Agent worker",
    "attribution still requires Cursor's agent worker to inherit this environment",
    "or expose a native session-start hook/source patch. This extension is not a",
    "launcher wrapper.",
  ];
  await vscode.window.showInformationMessage(lines.join("\n"), { modal: true });
}

function activate(context) {
  configureTerminalEnvironment(context);
  context.subscriptions.push(
    vscode.commands.registerCommand("agentSessionProvenance.check", checkEnvironment),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("agentSessionProvenance")) {
        configureTerminalEnvironment(context);
      }
    }),
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
