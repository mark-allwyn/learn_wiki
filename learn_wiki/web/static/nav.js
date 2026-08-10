// Shared top navigation. Include on every page:
//   <link rel="stylesheet" href="/static/theme.css" />
//   <div id="nav"></div>
//   <script defer src="/static/nav.js"></script>
(function () {
  var LINKS = [
    { label: "Graph", href: "/" },
    { label: "Wiki", href: "/wiki" },
  ];
  var el = document.getElementById("nav");
  if (!el) return;
  el.className = "nav";
  var path = location.pathname;
  el.innerHTML =
    '<span class="brand"><span class="mark">&#9672;</span> Knowledge Graph</span>' +
    '<span class="spacer"></span>' +
    LINKS.map(function (l) {
      var active = path === l.href ? " active" : "";
      return '<a class="tab' + active + '" href="' + l.href + '">' + l.label + "</a>";
    }).join("");
})();
