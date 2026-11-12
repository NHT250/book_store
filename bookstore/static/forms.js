// Browser-side validation and confirmation dialogs. The server re-validates everything.
(function () {
  "use strict";
  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  function showError(input, message) {
    var id = "cerr-" + input.name;
    var el = document.getElementById(id);
    if (!message) { if (el) el.remove(); input.removeAttribute("aria-invalid"); return; }
    if (!el) {
      el = document.createElement("p");
      el.className = "field-error";
      el.id = id;
      el.setAttribute("role", "alert");
      input.insertAdjacentElement("afterend", el);
    }
    el.textContent = message;
    input.setAttribute("aria-invalid", "true");
  }

  function check(input, form) {
    var v = input.type === "file" ? "" : (input.value || "").trim();
    if (input.hasAttribute("required") && !v && input.type !== "file") return "This field is required.";
    if (input.type === "email" && v && !EMAIL_RE.test(v)) return "Enter a valid email address.";
    var min = input.getAttribute("minlength"), max = input.getAttribute("maxlength");
    if (input.type === "password" && v && min && max && (v.length < +min || v.length > +max))
      return "Password must be between " + min + " and " + max + " characters.";
    if (input.type === "number" && v !== "") {
      if (!/^-?\d+$/.test(v)) return "Enter a whole number.";
      var nmin = input.getAttribute("min");
      if (nmin !== null && +v < +nmin) return +nmin > 0 ? "Must be greater than 0." : "Cannot be negative.";
    }
    var match = input.dataset.match;
    if (match && form.elements[match] && input.value !== form.elements[match].value)
      return "Password confirmation does not match.";
    if (input.hasAttribute("data-cover-required")) {
      var url = form.elements["cover_url"];
      if (!input.files.length && !(url && url.value.trim())) return "A cover image (upload or URL) is required.";
    }
    return "";
  }

  document.querySelectorAll("form[data-validate]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var first = null;
      Array.prototype.forEach.call(form.elements, function (input) {
        if (!input.name || input.type === "hidden" || input.tagName === "BUTTON") return;
        var msg = check(input, form);
        showError(input, msg);
        if (msg && !first) first = input;
      });
      if (first) { e.preventDefault(); first.focus(); }
    });
  });

  document.querySelectorAll("form[data-price-form]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      var box = form.querySelector("[data-price-error]");
      var lo = form.elements["min_price"].value.trim(), hi = form.elements["max_price"].value.trim();
      var msg = "";
      if ((lo && +lo < 0) || (hi && +hi < 0)) msg = "Prices cannot be negative.";
      else if (lo && hi && +lo > +hi) msg = "Minimum price cannot be greater than maximum price.";
      box.hidden = !msg;
      box.textContent = msg;
      if (msg) e.preventDefault();
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
})();
