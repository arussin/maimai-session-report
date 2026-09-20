(function initializeProjectLinks() {
  "use strict";
  let data;
  try { data = JSON.parse(document.getElementById("report-data")?.textContent || "{}"); }
  catch { return; }
  if (data?.support !== true || document.querySelector(".support-card")) return;
  const footer = document.querySelector(".footer");
  if (!footer) return;

  // Activate with the shared checkout release after live Stripe verification.
  const supportAvailable = false;
  const checkoutUrl = "https://maimai.party/support.html";
  const repositoryUrl = "https://github.com/arussin/maimai-session-report";
  function link(label, url, className, icon) {
    const anchor = document.createElement("a");
    anchor.className = "project-action " + className;
    anchor.href = url; anchor.target = "_blank";
    anchor.rel = "noopener noreferrer"; anchor.referrerPolicy = "no-referrer";
    // Only bundled, constant SVG markup enters this template.
    anchor.innerHTML = icon;
    anchor.append(document.createTextNode(label));
    return anchor;
  }
  const card = document.createElement("aside");
  card.className = "support-card"; card.setAttribute("aria-label", "Project links");
  card.append(link("View on GitHub", repositoryUrl, "github-button", "<svg width=\"22\" height=\"22\" viewBox=\"0 0 16 16\" fill=\"currentColor\" aria-hidden=\"true\"><path d=\"M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82a7.65 7.65 0 0 1 2-.27c.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z\"/></svg>"));
  if (supportAvailable) {
    const group = document.createElement("div"); group.className = "support-button-group";
    const support = link("Support maimai.party", checkoutUrl, "creator-support-link", "<svg class=\"creator-support-heart\" width=\"22\" height=\"22\" viewBox=\"0 0 24 24\" aria-hidden=\"true\">\n<defs><linearGradient id=\"creator-support-heart-gradient\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\"><stop offset=\"0\" stop-color=\"#ed5053\"/><stop offset=\".24\" stop-color=\"#ed5053\"/><stop offset=\".24\" stop-color=\"#f39835\"/><stop offset=\".42\" stop-color=\"#f39835\"/><stop offset=\".42\" stop-color=\"#f2c62e\"/><stop offset=\".48\" stop-color=\"#f2c62e\"/><stop offset=\".48\" stop-color=\"#8aba3d\"/><stop offset=\".70\" stop-color=\"#8aba3d\"/><stop offset=\".70\" stop-color=\"#27a9e0\"/><stop offset=\"1\" stop-color=\"#27a9e0\"/></linearGradient></defs>\n<path fill=\"url(#creator-support-heart-gradient)\" d=\"M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z\"/></svg>");
    support.addEventListener("click", event => {
      if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      // Fixed URL only: no report data, referrer, opener, or shared window name.
      // noopener intentionally returns null, even when the window opens successfully.
      window.open(checkoutUrl, "_blank", "popup,width=540,height=780,noopener,noreferrer");
    });
    const provider = document.createElement("span"); provider.className = "support-button-provider";
    provider.append(document.createTextNode("Powered by "));
    const logo = document.createElement("img"); logo.alt = "Stripe";
    logo.width = 35; logo.height = 15; logo.src = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzYwIiBoZWlnaHQ9IjE1MSIgdmlld0JveD0iMCAwIDM2MCAxNTEiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMzYwIDc4LjIwMDFDMzYwIDUyLjYwMDEgMzQ3LjYgMzIuNDAwMSAzMjMuOSAzMi40MDAxQzMwMC4xIDMyLjQwMDEgMjg1LjcgNTIuNjAwMSAyODUuNyA3OC4wMDAxQzI4NS43IDEwOC4xIDMwMi43IDEyMy4zIDMyNy4xIDEyMy4zQzMzOSAxMjMuMyAzNDggMTIwLjYgMzU0LjggMTE2LjhWOTYuODAwMUMzNDggMTAwLjIgMzQwLjIgMTAyLjMgMzMwLjMgMTAyLjNDMzIwLjYgMTAyLjMgMzEyIDk4LjkwMDIgMzEwLjkgODcuMTAwMkgzNTkuOEMzNTkuOCA4NS44MDAyIDM2MCA4MC42MDAyIDM2MCA3OC4yMDAxWk0zMTAuNiA2OC43MDAxQzMxMC42IDU3LjQwMDIgMzE3LjUgNTIuNzAwMSAzMjMuOCA1Mi43MDAxQzMyOS45IDUyLjcwMDEgMzM2LjQgNTcuNDAwMiAzMzYuNCA2OC43MDAxSDMxMC42WiIgZmlsbD0iIzA2MUIzMSIvPgo8cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCIgZD0iTTI0Ny4xIDMyLjQwMDFDMjM3LjMgMzIuNDAwMSAyMzEgMzcuMDAwMSAyMjcuNSA0MC4yMDAxTDIyNi4yIDM0LjAwMDFIMjA0LjJWMTUwLjZMMjI5LjIgMTQ1LjNMMjI5LjMgMTE3QzIzMi45IDExOS42IDIzOC4yIDEyMy4zIDI0NyAxMjMuM0MyNjQuOSAxMjMuMyAyODEuMiAxMDguOSAyODEuMiA3Ny4yMDAxQzI4MS4xIDQ4LjIwMDEgMjY0LjYgMzIuNDAwMSAyNDcuMSAzMi40MDAxWk0yNDEuMSAxMDEuM0MyMzUuMiAxMDEuMyAyMzEuNyA5OS4yMDAxIDIyOS4zIDk2LjYwMDJMMjI5LjIgNTkuNTAwMUMyMzEuOCA1Ni42MDAxIDIzNS40IDU0LjYwMDIgMjQxLjEgNTQuNjAwMkMyNTAuMiA1NC42MDAyIDI1Ni41IDY0LjgwMDEgMjU2LjUgNzcuOTAwMUMyNTYuNSA5MS4zMDAxIDI1MC4zIDEwMS4zIDI0MS4xIDEwMS4zWiIgZmlsbD0iIzA2MUIzMSIvPgo8cGF0aCBmaWxsLXJ1bGU9ImV2ZW5vZGQiIGNsaXAtcnVsZT0iZXZlbm9kZCIgZD0iTTE2OS44IDI2LjVMMTk0LjkgMjEuMVYwLjgwMDA0OUwxNjkuOCA2LjEwMDA1VjI2LjVaIiBmaWxsPSIjMDYxQjMxIi8+CjxwYXRoIGQ9Ik0xOTQuOSAzNC4xMDAxSDE2OS44VjEyMS42SDE5NC45VjM0LjEwMDFaIiBmaWxsPSIjMDYxQjMxIi8+CjxwYXRoIGZpbGwtcnVsZT0iZXZlbm9kZCIgY2xpcC1ydWxlPSJldmVub2RkIiBkPSJNMTQyLjkgNDEuNTAwMUwxNDEuMyAzNC4xMDAxSDExOS43VjEyMS42SDE0NC43VjYyLjMwMDFDMTUwLjYgNTQuNjAwMSAxNjAuNiA1Ni4wMDAxIDE2My43IDU3LjEwMDFWMzQuMTAwMUMxNjAuNSAzMi45MDAxIDE0OC44IDMwLjcwMDEgMTQyLjkgNDEuNTAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik05Mi44OTk5IDEyLjQwMDFMNjguNDk5OSAxNy42MDAxTDY4LjM5OTkgOTcuNzAwMUM2OC4zOTk5IDExMi41IDc5LjQ5OTkgMTIzLjQgOTQuMjk5OSAxMjMuNEMxMDIuNSAxMjMuNCAxMDguNSAxMjEuOSAxMTEuOCAxMjAuMVY5OS44MDAxQzEwOC42IDEwMS4xIDkyLjc5OTkgMTA1LjcgOTIuNzk5OSA5MC45MDAxVjU1LjQwMDFIMTExLjhWMzQuMTAwMkg5Mi43OTk5TDkyLjg5OTkgMTIuNDAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPHBhdGggZmlsbC1ydWxlPSJldmVub2RkIiBjbGlwLXJ1bGU9ImV2ZW5vZGQiIGQ9Ik0yNS4zIDU5LjUwMDFDMjUuMyA1NS42MDAxIDI4LjUgNTQuMTAwMiAzMy44IDU0LjEwMDJDNDEuNCA1NC4xMDAyIDUxIDU2LjQwMDEgNTguNiA2MC41MDAxVjM3LjAwMDFDNTAuMyAzMy43MDAxIDQyLjEgMzIuNDAwMSAzMy44IDMyLjQwMDFDMTMuNSAzMi40MDAxIDAgNDMuMDAwMSAwIDYwLjcwMDFDMCA4OC4zMDAxIDM4IDgzLjkwMDEgMzggOTUuODAwMUMzOCAxMDAuNCAzNCAxMDEuOSAyOC40IDEwMS45QzIwLjEgMTAxLjkgOS41IDk4LjUwMDIgMS4xIDkzLjkwMDJWMTE3LjdDMTAuNCAxMjEuNyAxOS44IDEyMy40IDI4LjQgMTIzLjRDNDkuMiAxMjMuNCA2My41IDExMy4xIDYzLjUgOTUuMjAwMUM2My40IDY1LjQwMDEgMjUuMyA3MC43MDAxIDI1LjMgNTkuNTAwMVoiIGZpbGw9IiMwNjFCMzEiLz4KPC9zdmc+Cg==";
    provider.append(logo); group.append(support, provider); card.append(group);
  }
  footer.before(card);
})();
