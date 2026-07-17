/**
 * DriveBook embed loader — Shadow DOM isolation.
 *
 * <div id="drivebook-root"></div>
 * <script src="https://HOST/widget/embed.js"
 *   data-target="#drivebook-root"
 *   data-source="instagram"
 *   data-lang="ro"
 *   data-height="720"
 *   async></script>
 */
(function () {
  var script = document.currentScript;
  if (!script) return;

  var src = script.getAttribute("src") || "";
  var origin;
  try {
    origin = new URL(src, window.location.href).origin;
  } catch (e) {
    origin = window.location.origin;
  }

  var targetSel = script.getAttribute("data-target") || "#drivebook-root";
  var source = script.getAttribute("data-source") || "embed";
  var lang = script.getAttribute("data-lang") || "ro";
  var height = script.getAttribute("data-height") || "720";
  var mode = (script.getAttribute("data-mode") || "shadow").toLowerCase();
  var apiBase = script.getAttribute("data-api") || origin;

  function loadText(url) {
    return fetch(url, { credentials: "omit" }).then(function (r) {
      if (!r.ok) throw new Error("Failed to load " + url);
      return r.text();
    });
  }

  function loadScript(url) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = url;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  function mountShadow(host) {
    var shadow = host.attachShadow({ mode: "open" });
    host.style.display = "block";
    host.style.minHeight = height + "px";

    return Promise.all([
      loadText(origin + "/widget/widget.css"),
      loadScript(origin + "/widget/widget.js"),
    ]).then(function (parts) {
      var css = parts[0];
      var style = document.createElement("style");
      style.textContent = css;
      // Google font for airy BSM feel
      var font = document.createElement("link");
      font.rel = "stylesheet";
      font.href = "https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700&display=swap";
      document.head.appendChild(font);

      var wrap = document.createElement("div");
      shadow.appendChild(style);
      shadow.appendChild(wrap);
      window.DriveBookWidget.mount(wrap, {
        apiBase: apiBase,
        source: source,
        lang: lang,
        cssHref: origin + "/widget/widget.css",
      });
    });
  }

  function mountButton(host) {
    var a = document.createElement("a");
    a.href = origin + "/book?source=" + encodeURIComponent(source) + "&lang=" + encodeURIComponent(lang);
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = script.getAttribute("data-label") || "Book a lesson";
    a.style.cssText =
      "display:inline-flex;align-items:center;justify-content:center;padding:14px 22px;" +
      "background:#f9812a;color:#fff;border-radius:10px;font:700 15px/1 Titillium Web,system-ui,sans-serif;" +
      "text-decoration:none;";
    host.innerHTML = "";
    host.appendChild(a);
  }

  function boot() {
    var el = document.querySelector(targetSel);
    if (!el) {
      console.warn("[DriveBook] target not found:", targetSel);
      return;
    }
    if (mode === "button" || mode === "link") {
      mountButton(el);
      return;
    }
    mountShadow(el).catch(function (e) {
      el.textContent = "DriveBook embed error: " + e.message;
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  window.DriveBook = {
    open: function (src, langArg) {
      window.open(
        origin +
          "/book?source=" +
          encodeURIComponent(src || source) +
          "&lang=" +
          encodeURIComponent(langArg || lang),
        "_blank",
        "noopener"
      );
    },
    url: function (src, langArg) {
      return (
        origin +
        "/book?source=" +
        encodeURIComponent(src || source) +
        "&lang=" +
        encodeURIComponent(langArg || lang)
      );
    },
  };
})();
