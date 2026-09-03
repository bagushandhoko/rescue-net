(function () {
  const METHOD_BASE =
    location.origin +
    "/rescue-net-frappe/api/method";

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
          payload.message ||
          payload.exception ||
          "Frappe permission denied"
        );

      err.status = 403;
      err.payload = payload;

      throw err;
    }

    if (!response.ok) {
      const err =
        new Error(
          payload.message ||
          payload.exception ||
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
