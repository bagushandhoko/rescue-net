(function () {
  const METHOD_BASE =
    location.origin +
    "/rescue-net-frappe/api/method";

  // Frappe's own PermissionError message carries raw HTML meant for its
  // desk UI (e.g. "frappe.exceptions.PermissionError: <details><summary>
  // You are not permitted...</summary>Function X is not whitelisted.
  // </details>") — shown as-is, that's exactly what leaked onto several
  // guest-facing pages as a big ugly technical dump. Strip it down to
  // plain text before it ever becomes an Error message.
  function cleanServerMessage(raw, status) {
    if (status === 403) return "Perlu login untuk mengakses fitur ini.";
    return String(raw || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  }

  // CSRF (2026-10-25): a session that holds a Frappe CSRF token (e.g. after a
  // Google login) gets HTTP 400 on every POST that lacks it — logout, member
  // approval, any save. Every unsafe request to the Rescue-Net API on this page
  // (RN_FRAPPE.call AND the pages' own fetch() calls) gets the session's token
  // from session_info; a 400 refreshes it once and retries.
  const rawFetch = window.fetch.bind(window);
  let csrfToken = null, csrfLoading = null;
  function loadCsrf(force) {
    if (csrfToken && !force) return Promise.resolve(csrfToken);
    if (!csrfLoading) {
      csrfLoading = rawFetch(METHOD_BASE + "/rescue_net.api_auth.session_info",
        { credentials: "include", headers: { Accept: "application/json" } })
        .then(r => r.ok ? r.json() : {})
        .then(j => (csrfToken = ((j && j.message) || {}).csrf_token || null))
        .catch(() => null)
        .finally(() => { csrfLoading = null; });
    }
    return csrfLoading;
  }
  function needsCsrf(url, method) {
    if (!/^(POST|PUT|PATCH|DELETE)$/i.test(method || "GET")) return false;
    const u = String(url || "");
    return u.indexOf("/rescue-net-frappe/api/method/") !== -1 && !/\/api\/method\/login(\?|$)/.test(u);
  }
  function withToken(init, token) {
    const h = new Headers((init && init.headers) || {});
    h.set("X-Frappe-CSRF-Token", token);
    return Object.assign({}, init || {}, { headers: h });
  }
  window.fetch = async function (input, init) {
    const url = typeof input === "string" ? input : (input && input.url) || "";
    const method = (init && init.method) || (input && input.method) || "GET";
    if (typeof input !== "string" || !needsCsrf(url, method)) return rawFetch(input, init);
    let token = await loadCsrf(false);
    let res = await rawFetch(input, token ? withToken(init, token) : init);
    if (res.status === 400) {
      const fresh = await loadCsrf(true);
      if (fresh && fresh !== token) res = await rawFetch(input, withToken(init, fresh));
    }
    return res;
  };

  function encodeArgs(args = {}) {
    const params = new URLSearchParams();

    Object.entries(args).forEach(
      ([key, value]) => {
        if (
          value === undefined ||
          value === null ||
          value === ""
        ) {
          return;
        }

        if (typeof value === "object") {
          params.set(
            key,
            JSON.stringify(value)
          );
        } else {
          params.set(
            key,
            String(value)
          );
        }
      }
    );

    return params;
  }

  async function call(
    method,
    args = {},
    options = {}
  ) {
    const httpMethod =
      String(
        options.method || "GET"
      ).toUpperCase();

    const params =
      encodeArgs(args);

    let url =
      METHOD_BASE +
      "/" +
      method;

    const config = {
      method: httpMethod,
      credentials: "include",
      headers: {
        "Accept":
          "application/json"
      }
    };

    if (httpMethod === "GET") {
      if (params.toString()) {
        url +=
          "?" +
          params.toString();
      }
    } else {
      config.headers[
        "Content-Type"
      ] =
        "application/x-www-form-urlencoded";

      config.body =
        params.toString();
    }

    const response =
      await fetch(
        url,
        config
      );

    const text =
      await response.text();

    let payload = {};

    try {
      payload =
        text
          ? JSON.parse(text)
          : {};
    } catch (_) {
      // an HTML body here = the reverse proxy served an error page
      // (502/504 while the backend restarts, or a gateway timeout).
      var looksHtml = /^\s*<(?:!doctype|html)/i.test(text || "");
      var e = new Error(
        looksHtml
          ? "Server sedang tidak tersedia (mungkin sedang restart). Coba lagi sebentar."
          : "Frappe returned non-JSON: " + (text || "").slice(0, 300)
      );
      e.status = response.status;
      e.transient = looksHtml;
      throw e;
    }

    if (response.status === 401) {
      const err =
        new Error(
          "Frappe session expired"
        );

      err.status =
        response.status;

      err.payload =
        payload;

      window.dispatchEvent(
        new CustomEvent(
          "rn:auth-required",
          {
            detail: {
              status:
                response.status
            }
          }
        )
      );

      throw err;
    }

    if (response.status === 403) {
      const err =
        new Error(
          cleanServerMessage(
            payload.message || payload.exception,
            403
          ) || "Perlu login untuk mengakses fitur ini."
        );

      err.status = 403;
      err.payload = payload;

      throw err;
    }

    if (!response.ok) {
      const err =
        new Error(
          cleanServerMessage(
            payload.message || payload.exception,
            response.status
          ) ||
          `Frappe HTTP ${
            response.status
          }`
        );

      err.status =
        response.status;

      err.payload =
        payload;

      throw err;
    }

    return Object.prototype
      .hasOwnProperty.call(
        payload,
        "message"
      )
      ? payload.message
      : payload;
  }

  async function session() {
    try {
      return await call(
        "rescue_net.api_auth.session_info"
      );
    } catch (err) {
      if (
        err.status === 401 ||
        err.status === 403
      ) {
        return null;
      }

      throw err;
    }
  }

  function loginUrl() {
    const next =
      encodeURIComponent(
        location.pathname +
        location.search +
        location.hash
      );

    if (
      location.pathname.includes(
        "/pages/"
      )
    ) {
      return (
        "auth.html?next=" +
        next
      );
    }

    return (
      "pages/auth.html?next=" +
      next
    );
  }

  window.addEventListener(
    "rn:auth-required",
    () => {
      location.href =
        loginUrl();
    }
  );

  window.RN_FRAPPE = {
    call,
    session,
    loginUrl,
    methodBase:
      METHOD_BASE
  };
})();
