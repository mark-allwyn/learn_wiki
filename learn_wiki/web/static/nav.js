// learn_wiki/web/static/nav.js
// Shared top navigation. Include on every page:
//   <div id="nav"></div>
//   <script src="/static/nav.js"></script>
(function () {
  var LINKS = [
    { label: "Graph", href: "/" },
    { label: "Wiki", href: "/wiki" },
  ];
  var path = location.pathname;
  var el = document.getElementById("nav");
  if (!el) return;
  el.style.cssText =
    "display:flex;gap:4px;align-items:center;padding:6px 10px;" +
    "background:#0d1017;border-bottom:1px solid #1e2430;font-family:system-ui,sans-serif";
  var brand = document.createElement("span");
  brand.textContent = "Knowledge Graph Wiki";
  brand.style.cssText = "color:#e6e9ef;font-weight:600;font-size:13px;margin-right:14px";
  el.appendChild(brand);
  LINKS.forEach(function (link) {
    var a = document.createElement("a");
    a.textContent = link.label;
    a.href = link.href;
    var active = path === link.href;
    a.style.cssText =
      "color:" + (active ? "#fff" : "#aab2c0") + ";text-decoration:none;" +
      "font-size:13px;padding:4px 10px;border-radius:6px;" +
      "background:" + (active ? "#2f6feb" : "transparent");
    el.appendChild(a);
  });
})();
