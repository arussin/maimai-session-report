import reportHtml from "../.wrangler/report.generated.js";

import {privateHeadersFor} from "./security.js";
export {contentSecurityPolicyFor, permissionsPolicyFor} from "./security.js";

function headers(contentType) {
  return privateHeadersFor(reportHtml, {"Content-Type":contentType});
}

function textResponse(body, status, requestMethod) {
  return new Response(requestMethod === "HEAD" ? null : body, {
    status,
    headers: headers("text/plain; charset=utf-8"),
  });
}

export function handleRequest(request, env = {}) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    const response = textResponse("Method not allowed.\n", 405, request.method);
    response.headers.set("Allow", "GET, HEAD");
    return response;
  }

  const reportPath = env.REPORT_PATH || "/";
  const url = new URL(request.url);
  if (url.pathname !== reportPath) {
    return textResponse("Not found.\n", 404, request.method);
  }

  return new Response(request.method === "HEAD" ? null : reportHtml, {
    status: 200,
    headers: headers("text/html; charset=utf-8"),
  });
}

export default {
  fetch(request, env) {
    return handleRequest(request, env);
  },
};
