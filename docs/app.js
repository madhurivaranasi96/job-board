/* Temporary loader — restores board from last known-good commit */
(function () {
  var s = document.createElement("script");
  s.src = "https://cdn.jsdelivr.net/gh/madhurivaranasi96/job-board@e410d04e2a1baff3a0654b9f147783f88eeb6844/docs/app.js";
  s.onerror = function () {
    document.getElementById("main").innerHTML =
      '<div class="empty"><h2>Could not load app</h2><p>Please hard-refresh in a minute.</p></div>';
  };
  document.body.appendChild(s);
})();
