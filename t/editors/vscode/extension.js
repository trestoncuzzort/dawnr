// t/editors/vscode/extension.js -- ROADMAP 15.3 (client) and 15.5 (verdicts
// view). Plain JavaScript, no TypeScript build step: `npm install` pulls
// vscode-languageclient, and the extension loads it directly with
// require(), same as any other CommonJS VS Code extension.
//
// What this does, end to end: starts t/lsp.py (t/LSP.md) as a child
// process over stdio using vscode-languageclient's LanguageClient, so
// diagnostics/hover/definition/formatting are handled by the language
// client machinery with no code here; registers the "t.verify" command,
// which sends the server's own t/verify request (t/LSP.md) for the active
// file; and listens for the custom t/verdicts notification (t/LSP.md),
// rendering it in a TreeView ("t verdicts", package.json's view
// container) and a status bar item, per ROADMAP 15.5's rules: an absent
// kernel is shown as absent, never as a verdict; a provisional verdict is
// marked provisional; the witness is rendered as the text the server
// already sends (an input assignment or a loop exit state -- this file
// invents no rendering of its own for it).

const path = require("path");
const vscode = require("vscode");
const { LanguageClient, TransportKind } = require("vscode-languageclient/node");

let client;
let verdictsProvider;
let statusBarItem;

function resolveServerPath(config, workspaceFolder) {
  const configured = config.get("serverPath", "t/lsp.py");
  if (path.isAbsolute(configured)) {
    return configured;
  }
  const root = workspaceFolder ? workspaceFolder.uri.fsPath : vscode.workspace.rootPath;
  return path.join(root, configured);
}

// One node per kernel entry from the most recent t/verdicts notification.
// The whole render is driven by what the server sent -- this class adds
// no verdict of its own for a kernel the payload did not mention.
class VerdictsProvider {
  constructor() {
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
    this.uri = null;
    this.kernels = {};
  }

  setVerdicts(payload) {
    this.uri = payload.uri;
    this.kernels = payload.kernels || {};
    this._onDidChangeTreeData.fire();
  }

  agreementCount() {
    let n = 0;
    for (const name of Object.keys(this.kernels)) {
      const e = this.kernels[name];
      if (e.status === "ok" && e.real === "verified" && e.twin === "refuted") {
        n += 1;
      }
    }
    return n;
  }

  getTreeItem(element) {
    return element;
  }

  getChildren(element) {
    if (element) {
      return [];
    }
    const names = Object.keys(this.kernels).sort();
    return names.map((name) => this._itemFor(name, this.kernels[name]));
  }

  _itemFor(name, entry) {
    let label;
    let tooltip;
    if (!entry || entry.status === "absent") {
      // 15.5: an absent kernel is shown as absent, never as a verdict.
      label = `${name}: absent`;
      tooltip = "kernel binary not found on this box (t/LSP.md status: absent)";
    } else if (entry.status === "no_twin") {
      label = `${name}: no twin`;
      tooltip = "kernel present, but no twin-ladder witness for this task";
    } else {
      const real = entry.real;
      const twin = entry.twin;
      let text = `${name}: ${real} / ${twin}`;
      if (entry.twin_op) {
        text += ` (${entry.twin_op})`;
      }
      if (entry.provisional) {
        text += " (provisional)";
      }
      label = text;
      const lines = [`real: ${real}`, `twin: ${twin}`];
      if (entry.twin_op) {
        lines.push(`operator: ${entry.twin_op}`);
      }
      if (entry.witness) {
        lines.push(`witness: ${entry.witness}`);
      }
      if (real === "refuted" && entry.witness) {
        // A refuted real: the witness carries the kernel's own message
        // (t/LSP.md: "witness" is the one field this payload uses for
        // that text, real or twin side alike).
        lines.push(`kernel message: ${entry.witness}`);
      }
      if (entry.provisional) {
        lines.push("provisional: a flake_check run whose n calls did not all agree");
      }
      tooltip = lines.join("\n");
    }
    const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
    item.tooltip = tooltip;
    item.contextValue = "tVerdictKernel";
    return item;
  }
}

function updateStatusBar() {
  if (!statusBarItem) {
    return;
  }
  const n = verdictsProvider.agreementCount();
  const total = Object.keys(verdictsProvider.kernels).length;
  statusBarItem.text = `$(check) t: ${n}/${total} agree`;
  statusBarItem.show();
}

function activate(context) {
  const config = vscode.workspace.getConfiguration("t");
  const workspaceFolder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  const pythonPath = config.get("pythonPath", "python3");
  const serverPath = resolveServerPath(config, workspaceFolder);
  const kernels = config.get("kernels", [
    "dafny", "verus", "spark", "framac", "lean", "rocq", "fstar",
  ]);

  const serverOptions = {
    run: { command: pythonPath, args: [serverPath], transport: TransportKind.stdio },
    debug: { command: pythonPath, args: [serverPath], transport: TransportKind.stdio },
  };
  const clientOptions = {
    documentSelector: [{ scheme: "file", language: "t" }],
    initializationOptions: { kernels },
  };

  client = new LanguageClient("t", "t language server", serverOptions, clientOptions);

  verdictsProvider = new VerdictsProvider();
  const treeView = vscode.window.createTreeView("t.verdictsView", {
    treeDataProvider: verdictsProvider,
  });
  context.subscriptions.push(treeView);

  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  context.subscriptions.push(statusBarItem);

  client.start().then(() => {
    // t/LSP.md: t/verdicts is a custom notification, sent automatically
    // after every didSave and once per t/verify request.
    client.onNotification("t/verdicts", (payload) => {
      verdictsProvider.setVerdicts(payload);
      updateStatusBar();
    });
  });

  const verifyCommand = vscode.commands.registerCommand("t.verify", async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor || editor.document.languageId !== "t") {
      vscode.window.showWarningMessage("t.verify: no active .t file");
      return;
    }
    const uri = editor.document.uri.toString();
    const currentKernels = vscode.workspace.getConfiguration("t").get("kernels", kernels);
    await client.sendRequest("t/verify", { uri, kernels: currentKernels });
  });
  context.subscriptions.push(verifyCommand);

  context.subscriptions.push(client);
}

function deactivate() {
  if (!client) {
    return undefined;
  }
  return client.stop();
}

module.exports = { activate, deactivate };
