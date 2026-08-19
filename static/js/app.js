(() => {
  "use strict";

  const MIN_TEXT_LENGTH = 20;

  const tabText = document.getElementById("tab-text");
  const tabUrl = document.getElementById("tab-url");
  const panelText = document.getElementById("panel-text");
  const panelUrl = document.getElementById("panel-url");
  const textInput = document.getElementById("text-input");
  const urlInput = document.getElementById("url-input");
  const textCounter = document.getElementById("text-counter");
  const textError = document.getElementById("text-error");
  const urlError = document.getElementById("url-error");
  const form = document.getElementById("check-form");
  const submitBtn = document.getElementById("submit-btn");
  const btnSpinner = document.getElementById("btn-spinner");
  const btnLabel = document.getElementById("btn-label");
  const loadingText = document.getElementById("loading-text");
  const formError = document.getElementById("form-error");
  const resultSection = document.getElementById("result-section");

  let activeTab = "text";
  let isSubmitting = false;

  // ---------------- Tabs ----------------
  function setActiveTab(tab) {
    activeTab = tab;
    const isText = tab === "text";

    tabText.classList.toggle("active", isText);
    tabUrl.classList.toggle("active", !isText);
    tabText.setAttribute("aria-selected", String(isText));
    tabUrl.setAttribute("aria-selected", String(!isText));

    panelText.classList.toggle("hidden", !isText);
    panelUrl.classList.toggle("hidden", isText);

    hideFieldErrors();
  }

  tabText.addEventListener("click", () => setActiveTab("text"));
  tabUrl.addEventListener("click", () => setActiveTab("url"));

  // ---------------- Character counter ----------------
  textInput.addEventListener("input", () => {
    const len = textInput.value.length;
    textCounter.textContent = `${len} karakter (minimal ${MIN_TEXT_LENGTH})`;
  });

  function hideFieldErrors() {
    textError.classList.add("hidden");
    urlError.classList.add("hidden");
    formError.classList.add("hidden");
  }

  function showTextError(msg) {
    textError.textContent = msg;
    textError.classList.remove("hidden");
  }

  function showUrlError(msg) {
    urlError.textContent = msg;
    urlError.classList.remove("hidden");
  }

  function showFormError(msg) {
    formError.textContent = msg;
    formError.classList.remove("hidden");
  }

  // ---------------- Validation ----------------
  function isValidUrl(value) {
    try {
      const parsed = new URL(value);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch (_err) {
      return false;
    }
  }

  function validateInput() {
    hideFieldErrors();

    if (activeTab === "text") {
      const value = textInput.value.trim();
      if (!value) {
        showTextError("Teks tidak boleh kosong.");
        return null;
      }
      if (value.length < MIN_TEXT_LENGTH) {
        showTextError(`Teks terlalu pendek. Minimal ${MIN_TEXT_LENGTH} karakter.`);
        return null;
      }
      return { type: "text", content: value };
    }

    const value = urlInput.value.trim();
    if (!value) {
      showUrlError("URL tidak boleh kosong.");
      return null;
    }
    if (!isValidUrl(value)) {
      showUrlError("Masukkan URL yang valid, diawali dengan http:// atau https://");
      return null;
    }
    return { type: "url", content: value };
  }

  // ---------------- Submit ----------------
  function setLoading(loading) {
    isSubmitting = loading;
    submitBtn.disabled = loading;
    btnSpinner.classList.toggle("hidden", !loading);
    btnLabel.textContent = loading ? "Menganalisis..." : "Periksa Berita";
    loadingText.classList.toggle("hidden", !loading);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSubmitting) return;

    const payload = validateInput();
    if (!payload) return;

    formError.classList.add("hidden");
    resultSection.classList.add("hidden");
    setLoading(true);

    try {
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      let data;
      try {
        data = await response.json();
      } catch (_parseErr) {
        throw new Error("Respons server tidak valid.");
      }

      if (!response.ok || !data.success) {
        showFormError(data.message || "Terjadi kesalahan saat menganalisis informasi.");
        return;
      }

      renderResult(data);
      resultSection.classList.remove("hidden");
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showFormError("Tidak dapat terhubung ke server. Periksa koneksi Anda dan coba lagi.");
    } finally {
      setLoading(false);
    }
  });

  // ---------------- Rendering ----------------
  const STATUS_META = {
    "Kemungkinan Hoaks": { badge: "status-hoax", bar: "bar-hoax", icon: "&#9888;" },
    "Perlu Verifikasi": { badge: "status-warning", bar: "bar-warning", icon: "&#9432;" },
    "Valid": { badge: "status-valid", bar: "bar-valid", icon: "&#10003;" },
  };

  const INDICATOR_ICON = {
    good: "&#10003;",
    warning: "&#9888;",
    bad: "&#10007;",
    neutral: "&#8226;",
  };

  function renderResult(data) {
    document.getElementById("score-value").textContent = `${data.score}%`;

    const meta = STATUS_META[data.status] || STATUS_META["Perlu Verifikasi"];
    const badge = document.getElementById("status-badge");
    badge.className = `inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-semibold mb-2 ${meta.badge}`;
    document.getElementById("status-icon").innerHTML = meta.icon;
    document.getElementById("status-label").textContent = data.status;

    const bar = document.getElementById("score-bar");
    bar.className = `h-full rounded-full transition-all duration-700 ease-out ${meta.bar}`;
    requestAnimationFrame(() => {
      bar.style.width = `${data.score}%`;
    });

    document.getElementById("result-summary").textContent = data.summary || "";
    document.getElementById("result-recommendation").textContent = data.recommendation || "";

    const articleBox = document.getElementById("article-detail");
    if (data.article) {
      articleBox.classList.remove("hidden");
      document.getElementById("article-title").textContent = data.article.title || "-";
      document.getElementById("article-domain").textContent = data.article.domain || "-";
      document.getElementById("article-wordcount").textContent = data.article.word_count ?? "-";
      const urlEl = document.getElementById("article-url");
      urlEl.textContent = data.article.url || "-";
    } else {
      articleBox.classList.add("hidden");
    }

    const list = document.getElementById("indicator-list");
    list.innerHTML = "";
    (data.indicators || []).forEach((ind) => {
      const li = document.createElement("li");
      li.className = `indicator-row indicator-${ind.status || "neutral"}`;
      const icon = INDICATOR_ICON[ind.status] || INDICATOR_ICON.neutral;
      li.innerHTML = `
        <span class="indicator-icon">${icon}</span>
        <span>
          <span class="font-semibold text-slate-800">${escapeHtml(ind.name)}</span>
          <span class="block text-slate-500">${escapeHtml(ind.description)}</span>
        </span>
      `;
      list.appendChild(li);
    });
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }
})();
