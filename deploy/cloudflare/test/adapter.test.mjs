import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";

const ADAPTER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const GENERATOR = path.join(ADAPTER_ROOT, "scripts", "generate-config.mjs");
const GENERATED_REPORT_MODULE = path.join(ADAPTER_ROOT, ".wrangler", "report.generated.js");
const WRANGLER = path.join(ADAPTER_ROOT, "node_modules", "wrangler", "bin", "wrangler.js");
const BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com";
const SUPPORT_MARKER = '"provider":"buy_me_a_coffee"';

async function generate({ html = "<!doctype html><title>Fixture</title><p>private</p>", env = {} } = {}) {
  const temporaryDirectory = await mkdtemp(path.join(tmpdir(), "maimai-report-cloudflare-"));
  const reportFile = path.join(temporaryDirectory, "report.html");
  const configFile = path.join(temporaryDirectory, "wrangler.jsonc");
  await writeFile(reportFile, html, "utf8");
  const result = spawnSync(
    process.execPath,
    [GENERATOR, "--report", reportFile, "--output", configFile],
    {
      cwd: ADAPTER_ROOT,
      encoding: "utf8",
      env: {
        ...process.env,
        CLOUDFLARE_WORKER_NAME: "fictional-private-report",
        CLOUDFLARE_CUSTOM_DOMAIN: "report.example.invalid",
        CLOUDFLARE_REPORT_PATH: "/report.html",
        ...env,
      },
    },
  );
  return { temporaryDirectory, reportFile, configFile, result };
}

test("generator disables alternate public URLs, metrics, and observability", async () => {
  const generated = await generate();
  try {
    assert.equal(generated.result.status, 0, generated.result.stderr);
    const config = JSON.parse(await readFile(generated.configFile, "utf8"));
    assert.equal(config.workers_dev, false);
    assert.equal(config.preview_urls, false);
    assert.equal(config.send_metrics, false);
    assert.deepEqual(config.dependencies_instrumentation, { enabled: false });
    assert.deepEqual(config.observability, { enabled: false });
    assert.deepEqual(config.routes, [
      { pattern: "report.example.invalid", custom_domain: true },
    ]);
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("generator rejects reports with external HTTP URLs", async () => {
  const generated = await generate({
    html: '<!doctype html><script src="https://example.invalid/a.js"></script>',
  });
  try {
    assert.equal(generated.result.status, 2);
    assert.match(generated.result.stderr, /external HTTP\/HTTPS URL/u);
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("generator allows only the isolated Buy Me a Coffee frame origin", async () => {
  const approved = await generate({
    html:
      `<!doctype html><meta http-equiv="Content-Security-Policy" ` +
      `content="frame-src ${BUY_ME_A_COFFEE_ORIGIN}">` +
      `<script type="application/json">{"support":{${SUPPORT_MARKER}}}</script>`,
  });
  try {
    assert.equal(approved.result.status, 0, approved.result.stderr);
  } finally {
    await rm(approved.temporaryDirectory, { recursive: true, force: true });
  }

  const unapproved = await generate({
    html:
      `<!doctype html><meta http-equiv="Content-Security-Policy" ` +
      `content="frame-src ${BUY_ME_A_COFFEE_ORIGIN}">` +
      `<script type="application/json">{"support":{${SUPPORT_MARKER}}}</script>` +
      '<img src="https://example.invalid/tracker.png">',
  });
  try {
    assert.equal(unapproved.result.status, 2);
    assert.match(unapproved.result.stderr, /only one external URL/u);
  } finally {
    await rm(unapproved.temporaryDirectory, { recursive: true, force: true });
  }
});

test("generator requires exactly one routing mode", async () => {
  const generated = await generate({
    env: { CLOUDFLARE_CUSTOM_DOMAIN: "", CLOUDFLARE_ROUTE_PATTERN: "" },
  });
  try {
    assert.equal(generated.result.status, 2);
    assert.match(generated.result.stderr, /exactly one/u);
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("route mode retains the required zone ID", async () => {
  const generated = await generate({
    env: {
      CLOUDFLARE_CUSTOM_DOMAIN: "",
      CLOUDFLARE_ROUTE_PATTERN: "report.example.invalid/private/*",
      CLOUDFLARE_ZONE_ID: "0123456789abcdef0123456789abcdef",
      CLOUDFLARE_REPORT_PATH: "/private/report.html",
    },
  });
  try {
    assert.equal(generated.result.status, 0, generated.result.stderr);
    const config = JSON.parse(await readFile(generated.configFile, "utf8"));
    assert.deepEqual(config.routes, [
      {
        pattern: "report.example.invalid/private/*",
        zone_id: "0123456789abcdef0123456789abcdef",
      },
    ]);
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("route mode rejects a pattern that cannot reach the report path", async () => {
  const generated = await generate({
    env: {
      CLOUDFLARE_CUSTOM_DOMAIN: "",
      CLOUDFLARE_ROUTE_PATTERN: "report.example.invalid/private/*",
      CLOUDFLARE_ZONE_ID: "0123456789abcdef0123456789abcdef",
      CLOUDFLARE_REPORT_PATH: "/report.html",
    },
  });
  try {
    assert.equal(generated.result.status, 2);
    assert.match(generated.result.stderr, /does not cover CLOUDFLARE_REPORT_PATH/u);
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("generated Wrangler configuration bundles in dry-run mode", async () => {
  const generated = await generate();
  const adapterConfig = path.join(
    ADAPTER_ROOT,
    ".wrangler",
    `test-wrangler-${process.pid}.generated.jsonc`,
  );
  try {
    assert.equal(generated.result.status, 0, generated.result.stderr);
    const adapterGeneration = spawnSync(
      process.execPath,
      [GENERATOR, "--report", generated.reportFile, "--output", adapterConfig],
      {
        cwd: ADAPTER_ROOT,
        encoding: "utf8",
        env: {
          ...process.env,
          CLOUDFLARE_WORKER_NAME: "fictional-private-report",
          CLOUDFLARE_CUSTOM_DOMAIN: "report.example.invalid",
          CLOUDFLARE_REPORT_PATH: "/report.html",
        },
      },
    );
    assert.equal(adapterGeneration.status, 0, adapterGeneration.stderr);
    const dryRunDirectory = path.join(generated.temporaryDirectory, "dry-run");
    const dryRun = spawnSync(
      process.execPath,
      [
        WRANGLER,
        "deploy",
        "--dry-run",
        "--config",
        adapterConfig,
        "--outdir",
        dryRunDirectory,
      ],
      {
        cwd: ADAPTER_ROOT,
        encoding: "utf8",
        env: {
          ...process.env,
          XDG_CONFIG_HOME: path.join(generated.temporaryDirectory, "xdg"),
          WRANGLER_SEND_METRICS: "false",
          WRANGLER_SEND_ERROR_REPORTS: "false",
        },
      },
    );
    assert.equal(dryRun.status, 0, `${dryRun.stdout}\n${dryRun.stderr}`);
  } finally {
    await rm(adapterConfig, { force: true });
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});

test("worker serves only the configured path with restrictive headers", async () => {
  const generated = await generate();
  try {
    assert.equal(generated.result.status, 0, generated.result.stderr);
    assert.ok((await readFile(GENERATED_REPORT_MODULE, "utf8")).includes("private"));
    const workerUrl = `${pathToFileURL(path.join(ADAPTER_ROOT, "src", "worker.js")).href}?test=${Date.now()}`;
    const {
      contentSecurityPolicyFor,
      handleRequest,
      permissionsPolicyFor,
    } = await import(workerUrl);

    const response = handleRequest(new Request("https://report.example.invalid/report.html"), {
      REPORT_PATH: "/report.html",
    });
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "private, no-store, max-age=0");
    assert.equal(response.headers.get("x-frame-options"), "DENY");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(response.headers.get("referrer-policy"), "no-referrer");
    assert.match(response.headers.get("content-security-policy"), /connect-src 'none'/u);
    assert.match(response.headers.get("content-security-policy"), /frame-src 'none'/u);
    assert.match(response.headers.get("permissions-policy"), /camera=\(\)/u);
    assert.match(response.headers.get("permissions-policy"), /payment=\(\)/u);
    assert.equal(await response.text(), "<!doctype html><title>Fixture</title><p>private</p>");

    const supportHtml = `<script type="application/json">{${SUPPORT_MARKER}}</script>`;
    assert.match(
      contentSecurityPolicyFor(supportHtml),
      new RegExp(`frame-src ${BUY_ME_A_COFFEE_ORIGIN.replaceAll(".", "\\.")}`, "u"),
    );
    assert.match(
      permissionsPolicyFor(supportHtml),
      new RegExp(`payment=\\(self "${BUY_ME_A_COFFEE_ORIGIN.replaceAll(".", "\\.")}"\\)`, "u"),
    );

    const missing = handleRequest(new Request("https://report.example.invalid/"), {
      REPORT_PATH: "/report.html",
    });
    assert.equal(missing.status, 404);

    const post = handleRequest(
      new Request("https://report.example.invalid/report.html", { method: "POST" }),
      { REPORT_PATH: "/report.html" },
    );
    assert.equal(post.status, 405);
    assert.equal(post.headers.get("allow"), "GET, HEAD");
  } finally {
    await rm(generated.temporaryDirectory, { recursive: true, force: true });
  }
});
