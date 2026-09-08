import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { developerSupportEnabled } from "../src/security.js";

const ADAPTER_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_OUTPUT = path.join(ADAPTER_ROOT, ".wrangler", "wrangler.generated.jsonc");
const GENERATED_REPORT_MODULE = path.join(ADAPTER_ROOT, ".wrangler", "report.generated.js");
const WORKER_ENTRYPOINT = path.join(ADAPTER_ROOT, "src", "worker.js");
const BUY_ME_A_COFFEE_ORIGIN = "https://buymeacoffee.com";

function fail(message) {
  console.error(`Cloudflare configuration error: ${message}`);
  process.exitCode = 2;
  throw new Error(message);
}

function readArguments(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key !== "--report" && key !== "--output") {
      fail(`unknown option ${JSON.stringify(key)}; expected --report PATH [--output PATH]`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith("--")) {
      fail(`${key} requires a path`);
    }
    values.set(key, value);
    index += 1;
  }
  return values;
}

function requiredEnvironment(name) {
  const value = process.env[name]?.trim();
  if (!value) {
    fail(`${name} is required`);
  }
  return value;
}

function validateWorkerName(value) {
  if (value.length > 63 || !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/u.test(value)) {
    fail("CLOUDFLARE_WORKER_NAME must be 1-63 lowercase letters, digits, or dashes and cannot start or end with a dash");
  }
}

function validateHostname(value) {
  if (
    value.length > 253 ||
    value.includes("://") ||
    value.includes("/") ||
    value.includes("*") ||
    !/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/u.test(value)
  ) {
    fail("CLOUDFLARE_CUSTOM_DOMAIN must be one exact lowercase hostname without a scheme, path, port, or wildcard");
  }
}

function validateRoutePattern(value) {
  if (
    value.length > 512 ||
    /[\s?#]/u.test(value) ||
    (/^[a-z][a-z0-9+.-]*:\/\//u.test(value) && !/^https?:\/\//u.test(value))
  ) {
    fail("CLOUDFLARE_ROUTE_PATTERN must be a Cloudflare route without whitespace, a query, a fragment, or a non-HTTP scheme");
  }
  const withoutScheme = value.replace(/^https?:\/\//u, "");
  if (!withoutScheme.includes("/") || withoutScheme.startsWith("/")) {
    fail("CLOUDFLARE_ROUTE_PATTERN must contain a hostname and path, for example report.example.invalid/private/*");
  }
}

function routeCoversReportPath(routePattern, reportPath) {
  const withoutScheme = routePattern.replace(/^https?:\/\//u, "");
  const slashIndex = withoutScheme.indexOf("/");
  const pathPattern = withoutScheme.slice(slashIndex);
  const escaped = pathPattern
    .split("*")
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&"))
    .join(".*");
  return new RegExp(`^${escaped}$`, "u").test(reportPath);
}

function validateZoneId(value) {
  if (!/^[a-f0-9]{32}$/u.test(value)) {
    fail("CLOUDFLARE_ZONE_ID must be the 32-character hexadecimal ID for the route's zone");
  }
}

function validateReportPath(value) {
  if (
    !value.startsWith("/") ||
    value.length > 1024 ||
    /[\s?#*]/u.test(value) ||
    (value.length > 1 && value.endsWith("/"))
  ) {
    fail("CLOUDFLARE_REPORT_PATH must be / or an exact absolute URL path without whitespace, query, fragment, wildcard, or trailing slash");
  }
}

function validateReportExternalUrls(reportHtml) {
  const externalUrls = [...reportHtml.matchAll(/https?:\/\/[^\s"'<>;]+/giu)].map(
    (match) => match[0],
  );
  const supportEnabled = developerSupportEnabled(reportHtml);
  const policies = [...reportHtml.matchAll(
    /<meta http-equiv="Content-Security-Policy" content="([^"]*)"\s*\/?>/gu,
  )];
  const hasApprovedFramePolicy = policies.length === 1 && policies[0][1]
    .split(";")
    .some((directive) => directive.trim() === `frame-src ${BUY_ME_A_COFFEE_ORIGIN}`);
  const inlineScripts = [...reportHtml.matchAll(/<script>([\s\S]*?)<\/script>/gu)];
  const originDeclaration = `const origin = "${BUY_ME_A_COFFEE_ORIGIN}";`;
  const hasCheckoutOrigin = inlineScripts.some((script) => script[1].includes(originDeclaration));

  if (!supportEnabled && externalUrls.length > 0) {
    fail("the report contains an external HTTP/HTTPS URL and will not be published");
  }
  if (
    supportEnabled &&
    (externalUrls.length !== 2 || externalUrls.some((url) => url !== BUY_ME_A_COFFEE_ORIGIN) ||
      !hasApprovedFramePolicy || !hasCheckoutOrigin)
  ) {
    fail(
      "a support-enabled report may contain only the two fixed Buy Me a Coffee origin references in its frame CSP and checkout code",
    );
  }
}

function toConfigPath(fromDirectory, target) {
  const relative = path.relative(fromDirectory, target).replaceAll(path.sep, "/");
  return relative.startsWith(".") ? relative : `./${relative}`;
}

async function main() {
  const argumentsMap = readArguments(process.argv.slice(2));
  const reportArgument = argumentsMap.get("--report");
  if (!reportArgument) {
    fail("--report PATH is required");
  }

  const reportFile = path.resolve(process.cwd(), reportArgument);
  const outputFile = path.resolve(
    process.cwd(),
    argumentsMap.get("--output") ?? DEFAULT_OUTPUT,
  );
  const workerName = requiredEnvironment("CLOUDFLARE_WORKER_NAME");
  const customDomain = process.env.CLOUDFLARE_CUSTOM_DOMAIN?.trim() ?? "";
  const routePattern = process.env.CLOUDFLARE_ROUTE_PATTERN?.trim() ?? "";
  const zoneId = process.env.CLOUDFLARE_ZONE_ID?.trim() ?? "";
  const reportPath = process.env.CLOUDFLARE_REPORT_PATH?.trim() || "/";

  validateWorkerName(workerName);
  validateReportPath(reportPath);
  if (Boolean(customDomain) === Boolean(routePattern)) {
    fail("set exactly one of CLOUDFLARE_CUSTOM_DOMAIN or CLOUDFLARE_ROUTE_PATTERN");
  }

  let route;
  if (customDomain) {
    validateHostname(customDomain);
    route = { pattern: customDomain, custom_domain: true };
  } else {
    validateRoutePattern(routePattern);
    if (!routeCoversReportPath(routePattern, reportPath)) {
      fail(
        "CLOUDFLARE_ROUTE_PATTERN does not cover CLOUDFLARE_REPORT_PATH; " +
          "use a matching exact path or wildcard route",
      );
    }
    const requiredZoneId = zoneId || requiredEnvironment("CLOUDFLARE_ZONE_ID");
    validateZoneId(requiredZoneId);
    route = { pattern: routePattern, zone_id: requiredZoneId };
  }

  let reportHtml;
  try {
    reportHtml = await readFile(reportFile, "utf8");
  } catch (error) {
    fail(`could not read report file ${JSON.stringify(reportFile)} (${error.code ?? "unknown error"})`);
  }
  if (!/^\s*<!doctype html(?:\s|>)/iu.test(reportHtml)) {
    fail("the report must be a complete HTML document beginning with <!doctype html>");
  }
  validateReportExternalUrls(reportHtml);

  await mkdir(path.dirname(GENERATED_REPORT_MODULE), { recursive: true });
  const safelyEncodedReport = JSON.stringify(reportHtml)
    .replaceAll("\u2028", "\\u2028")
    .replaceAll("\u2029", "\\u2029");
  await writeFile(GENERATED_REPORT_MODULE, `export default ${safelyEncodedReport};\n`, {
    encoding: "utf8",
    mode: 0o600,
  });

  await mkdir(path.dirname(outputFile), { recursive: true });
  const configDirectory = path.dirname(outputFile);
  const config = {
    $schema: path.join(ADAPTER_ROOT, "node_modules", "wrangler", "config-schema.json"),
    name: workerName,
    main: toConfigPath(configDirectory, WORKER_ENTRYPOINT),
    compatibility_date: "2026-09-01",
    compatibility_flags: ["nodejs_compat"],
    workers_dev: false,
    preview_urls: false,
    send_metrics: false,
    dependencies_instrumentation: { enabled: false },
    observability: { enabled: false },
    logpush: false,
    vars: { REPORT_PATH: reportPath },
    routes: [route],
  };
  await writeFile(outputFile, `${JSON.stringify(config, null, 2)}\n`, {
    encoding: "utf8",
    mode: 0o600,
  });
  console.log(`Generated private-by-default Wrangler configuration at ${outputFile}`);
}

main().catch((error) => {
  if (!process.exitCode) {
    console.error(`Cloudflare configuration error: ${error.message}`);
    process.exitCode = 1;
  }
});
