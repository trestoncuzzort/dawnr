// Exercise the actual extension module with small VS Code API stand-ins.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

async function harness() {
  const callbacks = {};
  const document = { uri: { toString: () => "file:///project/probe.t" }, version: 1,
    languageId: "t", getText: () => "original text" };
  let provider;
  const status = { show() {}, hide() {} };
  const vscode = {
    EventEmitter: class { constructor() { this.event = () => {}; } fire() {} },
    TreeItem: class { constructor(label) { this.label = label; } },
    TreeItemCollapsibleState: { None: 0 }, StatusBarAlignment: { Left: 0 },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: "/project" } }], textDocuments: [document],
      getConfiguration: () => ({ get: (_key, fallback) => fallback }),
      onDidChangeTextDocument: fn => { callbacks.change = fn; return {}; },
      onDidCloseTextDocument: fn => { callbacks.close = fn; return {}; },
    },
    window: {
      activeTextEditor: { document },
      createTreeView: (_id, options) => { provider = options.treeDataProvider; return {}; },
      createStatusBarItem: () => status,
      onDidChangeActiveTextEditor: fn => { callbacks.switch = fn; return {}; },
      showWarningMessage() {},
    },
    commands: { registerCommand: () => ({}) },
  };
  const client = { LanguageClient: class {
    start() { return Promise.resolve(); }
    onNotification(_method, fn) { callbacks.verdict = fn; }
  }, TransportKind: { stdio: 0 } };
  const module = { exports: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "extension.js"), "utf8"), {
    module, require: name => name === "vscode" ? vscode
      : name === "vscode-languageclient/node" ? client : require(name),
  });
  module.exports.activate({ subscriptions: [] });
  await Promise.resolve();
  const payload = {
    uri: document.uri.toString(), version: document.version,
    document_sha256: crypto.createHash("sha256").update(document.getText()).digest("hex"),
    kernels: { dafny: { status: "ok", real: "verified", twin: "refuted", provisional: false } },
  };
  return { callbacks, document, provider, payload, vscode, status };
}

test("provisional results never increase agreement", async () => {
  const h = await harness();
  h.payload.kernels.dafny.provisional = true;
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 0);
});

test("matching confirmed result counts", async () => {
  const h = await harness();
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 1);
});

test("stale document version is ignored", async () => {
  const h = await harness();
  h.document.version = 2;
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 0);
});

test("changed text with reused version is ignored", async () => {
  const h = await harness();
  h.document.getText = () => "reopened with different text";
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 0);
});

test("results for another active document are ignored", async () => {
  const h = await harness();
  h.vscode.window.activeTextEditor = { document: { ...h.document,
    uri: { toString: () => "file:///project/other.t" } } };
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 0);
});

for (const event of ["change", "close", "switch"]) {
  test(`${event} clears displayed proof counts`, async () => {
    const h = await harness();
    h.callbacks.verdict(h.payload);
    assert.equal(h.provider.agreementCount(), 1);
    if (event === "switch") {
      h.vscode.window.activeTextEditor = { document: { ...h.document,
        uri: { toString: () => "file:///project/other.t" } } };
    }
    h.callbacks[event](event === "close" ? h.document : { document: h.document });
    assert.equal(h.provider.agreementCount(), 0);
    assert.match(h.status.text, /unverified/);
  });
}

test("switching back restores a still-current cached result", async () => {
  const h = await harness();
  h.callbacks.verdict(h.payload);
  h.vscode.window.activeTextEditor = { document: { ...h.document,
    uri: { toString: () => "file:///project/other.t" } } };
  h.callbacks.switch();
  assert.equal(h.provider.agreementCount(), 0);
  h.vscode.window.activeTextEditor = { document: h.document };
  h.callbacks.switch();
  assert.equal(h.provider.agreementCount(), 1);
});

test("unversioned results cannot be displayed as current proof", async () => {
  const h = await harness();
  delete h.payload.version;
  delete h.payload.document_sha256;
  h.callbacks.verdict(h.payload);
  assert.equal(h.provider.agreementCount(), 0);
});
