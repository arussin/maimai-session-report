(function initializeSupportCheckout() {
  "use strict";

  const raw = document.getElementById("report-data")?.textContent || "{}";
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return;
  }

  if (data?.support !== true) return;

  const id = "russin";
  const label = "Buy the developer a maimai credit";
  const description = "Support maimai Session Report";
  const color = "#5F7FFF";

  const reportFooter = document.querySelector(".footer");
  if (!reportFooter) return;

  function makeElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  const card = makeElement("aside", "support-card");
  card.setAttribute("aria-label", "Optional support");

  const copy = makeElement("div", "support-copy");
  copy.appendChild(makeElement("span", "support-kicker", "Optional support"));
  copy.appendChild(makeElement("span", "support-prompt", "Enjoying maimai Session Report?"));

  const actionGroup = makeElement("div", "support-action-group");
  const openButton = makeElement("button", "support-button");
  openButton.type = "button";
  openButton.style.setProperty("--support-color", color);
  openButton.setAttribute("aria-haspopup", "dialog");
  openButton.setAttribute("aria-controls", "support-checkout-dialog");
  const icon = makeElement("span", "support-button-icon", "♪");
  icon.setAttribute("aria-hidden", "true");
  openButton.appendChild(icon);
  openButton.appendChild(makeElement("span", "support-button-label", label));
  actionGroup.appendChild(openButton);
  actionGroup.appendChild(makeElement("span", "support-via", "via Buy Me a Coffee"));

  card.appendChild(copy);
  card.appendChild(actionGroup);
  reportFooter.before(card);

  const dialog = makeElement("dialog", "support-dialog");
  dialog.id = "support-checkout-dialog";
  dialog.setAttribute("aria-labelledby", "support-dialog-title");
  dialog.setAttribute("aria-describedby", "support-dialog-description");

  const dialogHeader = makeElement("header", "support-dialog-header");
  const headingGroup = makeElement("div", "support-dialog-heading");
  const heading = makeElement("h2", "support-dialog-title", label);
  heading.id = "support-dialog-title";
  const subheading = makeElement(
    "p",
    "support-dialog-description",
    "Secure checkout provided by Buy Me a Coffee."
  );
  subheading.id = "support-dialog-description";
  headingGroup.appendChild(heading);
  headingGroup.appendChild(subheading);

  const closeButton = makeElement("button", "support-dialog-close", "×");
  closeButton.type = "button";
  closeButton.setAttribute("aria-label", "Close support checkout");
  dialogHeader.appendChild(headingGroup);
  dialogHeader.appendChild(closeButton);

  const frameWrap = makeElement("div", "support-frame-wrap");
  const loading = makeElement("div", "support-loading");
  loading.setAttribute("role", "status");
  loading.appendChild(makeElement("span", "support-loading-ring"));
  loading.appendChild(makeElement("span", "support-loading-copy", "Opening secure checkout…"));

  const frame = document.createElement("iframe");
  frame.className = "support-frame";
  frame.title = "Buy Me a Coffee support checkout";
  // The parent HTTP Permissions-Policy constrains payment to Buy Me a Coffee.
  // Keeping the iframe delegation broad avoids losing wallet support if BMC
  // changes an internal navigation while leaving the parent allowlist strict.
  frame.allow = "payment *";
  frame.loading = "lazy";
  frame.referrerPolicy = "no-referrer";
  frameWrap.appendChild(loading);
  frameWrap.appendChild(frame);

  const dialogFooter = makeElement("footer", "support-dialog-footer");
  dialogFooter.appendChild(
    makeElement("span", "support-privacy-note", "Payment details never pass through this report.")
  );
  const fallback = makeElement("a", "support-fallback", "Open separately ↗");
  fallback.target = "_blank";
  fallback.rel = "noopener noreferrer";
  fallback.referrerPolicy = "no-referrer";
  dialogFooter.appendChild(fallback);

  dialog.appendChild(dialogHeader);
  dialog.appendChild(frameWrap);
  dialog.appendChild(dialogFooter);
  document.body.appendChild(dialog);

  const origin = "https://buymeacoffee.com";
  fallback.href = `${origin}/${encodeURIComponent(id)}`;

  let frameStarted = false;
  function startCheckout() {
    if (frameStarted) return;
    const url = new URL(`${origin}/widget/page/${encodeURIComponent(id)}`);
    url.searchParams.set("description", description);
    url.searchParams.set("color", color);
    frame.src = url.toString();
    frameStarted = true;
  }

  function openCheckout() {
    startCheckout();
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "");
    }
    document.body.classList.add("support-dialog-open");
    closeButton.focus();
  }

  function closeCheckout() {
    if (typeof dialog.close === "function" && dialog.open) {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
      document.body.classList.remove("support-dialog-open");
      openButton.focus();
    }
  }

  openButton.addEventListener("click", openCheckout);
  closeButton.addEventListener("click", closeCheckout);
  frame.addEventListener("load", () => {
    loading.hidden = true;
  });
  dialog.addEventListener("close", () => {
    document.body.classList.remove("support-dialog-open");
    openButton.focus();
  });
  dialog.addEventListener("cancel", () => {
    document.body.classList.remove("support-dialog-open");
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) closeCheckout();
  });
})();
