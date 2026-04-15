window.APP_CONFIG = window.APP_CONFIG || {};

if (!window.APP_CONFIG.API_BASE) {
  window.APP_CONFIG.API_BASE = "http://127.0.0.1:8000";
}

(function () {
  var nativeAlert = window.alert ? window.alert.bind(window) : function () {};
  var uiReady = false;
  var toastEl = null;
  var toastTextEl = null;
  var toastTimer = null;
  var confirmEl = null;
  var confirmTextEl = null;
  var confirmOkEl = null;
  var confirmCancelEl = null;
  var confirmBackdropEl = null;

  function ensureUi() {
    if (uiReady || !document.body) return uiReady;

    var style = document.createElement("style");
    style.id = "app-ui-feedback-style";
    style.textContent = ""
      + ".app-ui-toast{position:fixed;right:16px;top:16px;z-index:2147483646;display:none;align-items:center;gap:10px;min-width:260px;max-width:min(420px,calc(100vw - 32px));padding:10px 12px;border-radius:12px;border:1px solid rgba(148,163,184,.35);background:rgba(255,255,255,.98);box-shadow:0 18px 36px rgba(15,23,42,.22);opacity:0;transform:translateY(-8px);transition:all .24s ease;font-family:Segoe UI,sans-serif}"
      + ".app-ui-toast.show{display:flex;opacity:1;transform:translateY(0)}"
      + ".app-ui-toast img{width:32px;height:32px;border-radius:8px;padding:5px;background:#ecfeff;border:1px solid #bae6fd;object-fit:contain;flex:0 0 32px}"
      + ".app-ui-toast p{margin:0;color:#0f172a;font-size:13px;font-weight:700;line-height:1.5}"
      + ".app-ui-toast.success{background:rgba(240,253,250,.98);border-color:rgba(16,185,129,.4)}"
      + ".app-ui-toast.error{background:rgba(255,241,242,.98);border-color:rgba(244,63,94,.4)}"
      + ".app-ui-confirm{position:fixed;inset:0;display:none;align-items:center;justify-content:center;z-index:2147483645;padding:16px;font-family:Segoe UI,sans-serif}"
      + ".app-ui-confirm.show{display:flex}"
      + ".app-ui-confirm-backdrop{position:absolute;inset:0;background:rgba(15,23,42,.38);backdrop-filter:blur(2px)}"
      + ".app-ui-confirm-card{position:relative;width:min(460px,calc(100vw - 30px));border-radius:16px;border:1px solid rgba(148,163,184,.4);background:linear-gradient(170deg,rgba(255,255,255,.98),rgba(248,250,252,.95));box-shadow:0 24px 45px rgba(15,23,42,.24);padding:16px}"
      + ".app-ui-confirm-head{display:flex;align-items:center;gap:10px;margin-bottom:8px}"
      + ".app-ui-confirm-logo{width:40px;height:40px;border-radius:10px;padding:7px;background:#ecfeff;border:1px solid #bae6fd;object-fit:contain}"
      + ".app-ui-confirm-title{margin:0;font-size:16px;font-weight:900;color:#0f172a}"
      + ".app-ui-confirm-text{margin:0;color:#334155;line-height:1.6;font-size:14px;font-weight:600}"
      + ".app-ui-confirm-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:14px}"
      + ".app-ui-confirm-btn{border:none;border-radius:10px;padding:9px 12px;font-size:13px;font-weight:800;cursor:pointer}"
      + ".app-ui-confirm-btn.cancel{background:#e2e8f0;color:#0f172a}"
      + ".app-ui-confirm-btn.ok{background:#0f766e;color:#fff}";
    document.head.appendChild(style);

    toastEl = document.createElement("div");
    toastEl.className = "app-ui-toast";
    toastEl.innerHTML = "<img src=\"intellibuild-mark.svg\" alt=\"IntelliBuild\"><p></p>";
    toastTextEl = toastEl.querySelector("p");
    document.body.appendChild(toastEl);

    confirmEl = document.createElement("div");
    confirmEl.className = "app-ui-confirm";
    confirmEl.innerHTML = ""
      + "<div class=\"app-ui-confirm-backdrop\"></div>"
      + "<div class=\"app-ui-confirm-card\" role=\"dialog\" aria-modal=\"true\" aria-label=\"Confirmation\">"
      + "<div class=\"app-ui-confirm-head\">"
      + "<img class=\"app-ui-confirm-logo\" src=\"intellibuild-mark.svg\" alt=\"IntelliBuild\">"
      + "<h3 class=\"app-ui-confirm-title\">Confirmer l'action</h3>"
      + "</div>"
      + "<p class=\"app-ui-confirm-text\">Confirmer cette action ?</p>"
      + "<div class=\"app-ui-confirm-actions\">"
      + "<button type=\"button\" class=\"app-ui-confirm-btn cancel\">Annuler</button>"
      + "<button type=\"button\" class=\"app-ui-confirm-btn ok\">Confirmer</button>"
      + "</div>"
      + "</div>";
    document.body.appendChild(confirmEl);

    confirmBackdropEl = confirmEl.querySelector(".app-ui-confirm-backdrop");
    confirmTextEl = confirmEl.querySelector(".app-ui-confirm-text");
    confirmOkEl = confirmEl.querySelector(".app-ui-confirm-btn.ok");
    confirmCancelEl = confirmEl.querySelector(".app-ui-confirm-btn.cancel");

    uiReady = true;
    return true;
  }

  function showToast(message, type) {
    if (!ensureUi()) {
      nativeAlert(String(message || "Information"));
      return;
    }
    if (toastTimer) {
      clearTimeout(toastTimer);
      toastTimer = null;
    }
    toastEl.classList.remove("success", "error", "show");
    toastEl.classList.add(type === "error" ? "error" : "success");
    toastTextEl.textContent = String(message || "Operation terminee");
    toastEl.classList.add("show");
    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");
    }, 2600);
  }

  window.appUiAlert = function (message, type) {
    showToast(message, type || "success");
  };

  window.appUiConfirm = function (message) {
    return new Promise(function (resolve) {
      if (!ensureUi()) {
        resolve(window.confirm(String(message || "Confirmer cette action ?")));
        return;
      }

      confirmTextEl.textContent = String(message || "Confirmer cette action ?");
      confirmEl.classList.add("show");

      function close(answer) {
        confirmEl.classList.remove("show");
        confirmOkEl.removeEventListener("click", onOk);
        confirmCancelEl.removeEventListener("click", onCancel);
        confirmBackdropEl.removeEventListener("click", onCancel);
        resolve(answer);
      }

      function onOk() { close(true); }
      function onCancel() { close(false); }

      confirmOkEl.addEventListener("click", onOk);
      confirmCancelEl.addEventListener("click", onCancel);
      confirmBackdropEl.addEventListener("click", onCancel);
    });
  };

  window.alert = function (message) {
    var text = String(message || "").toLowerCase();
    var looksError = text.indexOf("erreur") >= 0
      || text.indexOf("impossible") >= 0
      || text.indexOf("invalide") >= 0
      || text.indexOf("echec") >= 0
      || text.indexOf("failed") >= 0
      || text.indexOf("error") >= 0;
    showToast(message, looksError ? "error" : "success");
  };
})();

(function () {
  var sidebarStyleReady = false;
  var profileRequest = null;

  function whenReady(callback) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", callback, { once: true });
      return;
    }
    callback();
  }

  function getLocale() {
    return String(localStorage.getItem("lang") || document.documentElement.lang || "fr").toLowerCase();
  }

  function sidebarText(key) {
    var locale = getLocale();
    var copy = {
      fr: {
        admin: "Administrateur",
        user: "Utilisateur",
        profile: "Consulter le profil"
      },
      en: {
        admin: "Administrator",
        user: "User",
        profile: "Open profile"
      },
      ar: {
        admin: "مشرف",
        user: "مستخدم",
        profile: "عرض الملف الشخصي"
      }
    };
    var langPack = copy[locale] || copy.fr;
    return langPack[key] || copy.fr[key] || "";
  }

  function scopedKey(base, userId) {
    return base + ":" + String(userId || "anonymous");
  }

  function titleCase(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/\b\w/g, function (char) { return char.toUpperCase(); });
  }

  function displayNameFromEmail(email, fallback) {
    var source = String(email || "").split("@")[0].replace(/[._-]+/g, " ").trim();
    if (!source) return fallback || "Utilisateur";
    return titleCase(source);
  }

  function getStoredProfile(roleHint) {
    var role = String(roleHint || localStorage.getItem("userRole") || document.documentElement.getAttribute("data-role") || "user").toLowerCase();
    var email = String(localStorage.getItem("userEmail") || "").trim();
    var userId = String(localStorage.getItem("userId") || "").trim();
    var scopedName = userId ? String(localStorage.getItem(scopedKey("userDisplayName", userId)) || "").trim() : "";
    var fallbackName = role === "admin" ? sidebarText("admin") : sidebarText("user");
    var displayName = scopedName
      || String(localStorage.getItem("userDisplayName") || "").trim()
      || displayNameFromEmail(email, fallbackName);

    return {
      id: userId,
      email: email,
      role: role,
      display_name: displayName
    };
  }

  function syncProfileStorage(profile) {
    if (!profile || typeof profile !== "object") return getStoredProfile();

    var email = String(profile.email || localStorage.getItem("userEmail") || "").trim();
    var role = String(profile.role || localStorage.getItem("userRole") || "user").toLowerCase();
    var userId = String(profile.id || localStorage.getItem("userId") || "").trim();
    var scopedName = userId ? String(localStorage.getItem(scopedKey("userDisplayName", userId)) || "").trim() : "";
    var displayName = scopedName
      || String(localStorage.getItem("userDisplayName") || "").trim()
      || String(profile.display_name || "").trim()
      || displayNameFromEmail(email, role === "admin" ? sidebarText("admin") : sidebarText("user"));

    if (email) localStorage.setItem("userEmail", email);
    if (role) localStorage.setItem("userRole", role);
    if (displayName) localStorage.setItem("userDisplayName", displayName);
    if (userId) {
      localStorage.setItem("userId", userId);
      localStorage.setItem(scopedKey("userDisplayName", userId), displayName);
    }

    return {
      id: userId,
      email: email,
      role: role,
      display_name: displayName
    };
  }

  function inferSidebarRole(aside) {
    if (!aside) return String(document.documentElement.getAttribute("data-role") || localStorage.getItem("userRole") || "user").toLowerCase();

    var className = String(aside.className || "").toLowerCase();
    if (className.indexOf("doc-admin-sidebar") >= 0) return "admin";
    if (className.indexOf("doc-user-sidebar") >= 0) return "user";

    var hrefs = Array.prototype.map.call(
      aside.querySelectorAll("nav a[href]"),
      function (link) { return String(link.getAttribute("href") || "").toLowerCase(); }
    );

    var userMatch = hrefs.some(function (href) {
      return href.indexOf("user.html") >= 0
        || href.indexOf("mesobjet") >= 0
        || href.indexOf("localisations-user") >= 0
        || href.indexOf("notifications-user") >= 0
        || href.indexOf("parametres-user") >= 0;
    });

    if (userMatch) return "user";

    var adminMatch = hrefs.some(function (href) {
      return href.indexOf("ajouter-objet") >= 0
        || href.indexOf("objets.html") >= 0
        || href.indexOf("localisations.html") >= 0
        || href.indexOf("notifications-admin") >= 0
        || href.indexOf("parametres.html") >= 0
        || href === "index.html";
    });

    if (adminMatch) return "admin";

    return String(document.documentElement.getAttribute("data-role") || localStorage.getItem("userRole") || "user").toLowerCase();
  }

  function isAppSidebar(aside) {
    if (!aside) return false;
    if (!aside.querySelector("nav a")) return false;
    if (!(aside.querySelector(".logo") || aside.querySelector(".sidebar-logo") || aside.querySelector('img[src*="intellibuild-mark"]'))) return false;
    return String(aside.className || "").toLowerCase().indexOf("sidebar") >= 0;
  }

  function ensureSidebarStyle() {
    if (sidebarStyleReady || document.getElementById("sidebar-profile-style")) return;

    var style = document.createElement("style");
    style.id = "sidebar-profile-style";
    style.textContent = ""
      + ".sidebar-profile-card{display:grid;grid-template-columns:44px minmax(0,1fr) 40px;align-items:center;gap:12px;padding:10px 12px;margin:12px 0 10px;border-radius:20px;text-decoration:none;color:#fff;background:linear-gradient(180deg,rgba(71,85,105,.42),rgba(30,41,59,.78));border:1px solid rgba(255,255,255,.16);box-shadow:0 12px 20px rgba(2,6,23,.18),inset 0 1px 0 rgba(255,255,255,.08);backdrop-filter:blur(12px);transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}"
      + ".sidebar-profile-card:hover{transform:translateY(-1px);border-color:rgba(255,255,255,.24);box-shadow:0 16px 26px rgba(2,6,23,.22),inset 0 1px 0 rgba(255,255,255,.1)}"
      + ".sidebar-profile-avatar{width:44px;height:44px;border-radius:999px;display:grid;place-items:center;background:linear-gradient(135deg,#8fd3ff,#60a5fa);color:#0f172a;font-size:15px;font-weight:900;box-shadow:inset 0 0 0 3px rgba(255,255,255,.22)}"
      + ".sidebar-profile-copy{display:grid;gap:2px;min-width:0}"
      + ".sidebar-profile-name{font-size:14px;font-weight:800;line-height:1.15;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}"
      + ".sidebar-profile-role{font-size:12px;font-weight:600;line-height:1.2;color:rgba(255,255,255,.8);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
      + ".sidebar-profile-action{width:40px;height:40px;border-radius:14px;display:grid;place-items:center;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.12);color:rgba(255,255,255,.9);font-size:14px}"
      + ".sidebar-profile-card:focus-visible{outline:2px solid rgba(125,211,252,.92);outline-offset:3px}"
      + ".sidebar-profile-compact .sidebar-profile-card{margin:12px 0 10px}"
      + "@media (max-width:1080px){.sidebar-profile-card{margin:12px 0 10px}}";
    document.head.appendChild(style);
    sidebarStyleReady = true;
  }

  function buildProfileHref(role) {
    return role === "admin" ? "parametres.html#profileSection" : "parametres-user.html#profileSection";
  }

  function updateProfileCard(card, profile, roleHint) {
    if (!card) return;

    var role = String(roleHint || card.getAttribute("data-profile-role") || "user").toLowerCase();
    var profileData = profile || getStoredProfile(role);
    var email = String(profileData.email || localStorage.getItem("userEmail") || "").trim();
    var displayName = String(profileData.display_name || "").trim()
      || displayNameFromEmail(email, role === "admin" ? sidebarText("admin") : sidebarText("user"));
    var effectiveRole = String(profileData.role || role).toLowerCase() === "admin" ? "admin" : role;
    var initial = (displayName.charAt(0) || (effectiveRole === "admin" ? "A" : "U")).toUpperCase();

    card.setAttribute("href", buildProfileHref(role));
    card.setAttribute("title", sidebarText("profile"));

    var avatar = card.querySelector(".sidebar-profile-avatar");
    var name = card.querySelector(".sidebar-profile-name");
    var roleLabel = card.querySelector(".sidebar-profile-role");

    if (avatar) avatar.textContent = initial;
    if (name) name.textContent = displayName;
    if (roleLabel) roleLabel.textContent = effectiveRole === "admin" ? sidebarText("admin") : sidebarText("user");
  }

  function mountProfileCard(aside) {
    if (!aside || aside.querySelector("[data-sidebar-profile-card]")) return;

    var role = inferSidebarRole(aside);
    if (role !== "admin" && role !== "user") return;

    ensureSidebarStyle();

    var card = document.createElement("a");
    card.className = "sidebar-profile-card";
    card.setAttribute("data-sidebar-profile-card", "true");
    card.setAttribute("data-profile-role", role);
    card.setAttribute("aria-label", sidebarText("profile"));
    card.innerHTML = ""
      + "<span class=\"sidebar-profile-avatar\">" + (role === "admin" ? "A" : "U") + "</span>"
      + "<span class=\"sidebar-profile-copy\">"
      + "<strong class=\"sidebar-profile-name\">" + (role === "admin" ? sidebarText("admin") : sidebarText("user")) + "</strong>"
      + "<span class=\"sidebar-profile-role\">" + (role === "admin" ? sidebarText("admin") : sidebarText("user")) + "</span>"
      + "</span>"
      + "<span class=\"sidebar-profile-action\" aria-hidden=\"true\"><i class=\"fas fa-sliders-h\"></i></span>";

    var bottom = aside.querySelector(".sidebar-bottom");
    var topWrapper = Array.prototype.find.call(aside.children, function (child) {
      return child && child.querySelector && child.querySelector("nav");
    });
    var wrappedNav = topWrapper && topWrapper.querySelector ? topWrapper.querySelector("nav") : null;
    var insertionHost = topWrapper || aside;
    var directBrand = Array.prototype.find.call(insertionHost.children || [], function (child) {
      if (!child || !child.tagName) return false;
      var className = String(child.className || "").toLowerCase();
      if (className.indexOf("logo") >= 0) return true;
      if (child.querySelector && child.querySelector('img[src*="intellibuild-mark"]') && !child.querySelector("nav")) return true;
      return false;
    });
    var directNav = Array.prototype.find.call(aside.children, function (child) {
      return child && child.tagName && child.tagName.toLowerCase() === "nav";
    });

    if (directBrand && directBrand.parentNode === insertionHost) {
      if (directBrand.nextSibling) {
        insertionHost.insertBefore(card, directBrand.nextSibling);
      } else {
        insertionHost.appendChild(card);
      }
      aside.classList.add("sidebar-profile-compact");
    } else if (wrappedNav && topWrapper) {
      topWrapper.insertBefore(card, wrappedNav);
      aside.classList.add("sidebar-profile-compact");
    } else if (directNav) {
      aside.insertBefore(card, directNav);
      aside.classList.add("sidebar-profile-compact");
    } else if (bottom && bottom.parentNode === aside) {
      aside.insertBefore(card, bottom);
      aside.classList.add("sidebar-profile-compact");
    } else {
      var nav = aside.querySelector("nav");
      if (nav && nav.parentNode) {
        nav.parentNode.insertBefore(card, nav);
      } else {
        aside.appendChild(card);
      }
    }

    updateProfileCard(card, getStoredProfile(role), role);
  }

  function fetchCurrentProfile() {
    if (profileRequest) return profileRequest;

    var token = String(localStorage.getItem("userToken") || "").trim();
    if (!token) return Promise.resolve(null);

    var apiBase = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "http://127.0.0.1:8000";
    profileRequest = fetch(apiBase + "/user/profile", {
      method: "GET",
      headers: {
        "Authorization": "Bearer " + token
      }
    })
      .then(function (response) {
        if (!response.ok) throw new Error("profile_request_failed");
        return response.json();
      })
      .then(function (profile) {
        return syncProfileStorage(profile);
      })
      .catch(function () {
        return null;
      });

    return profileRequest;
  }

  function initSidebarProfiles() {
    // Include both <aside> elements and elements using the legacy `.sidebar` class
    // (some pages like `user.html` use a <div class="sidebar"> instead of <aside>).
    var sidebars = Array.prototype.filter.call(document.querySelectorAll("aside, .sidebar"), isAppSidebar);
    if (!sidebars.length) return;

    sidebars.forEach(mountProfileCard);

    Array.prototype.forEach.call(document.querySelectorAll("[data-sidebar-profile-card]"), function (card) {
      updateProfileCard(card, null, card.getAttribute("data-profile-role"));
    });

    fetchCurrentProfile().then(function (profile) {
      if (!profile) return;
      Array.prototype.forEach.call(document.querySelectorAll("[data-sidebar-profile-card]"), function (card) {
        updateProfileCard(card, profile, card.getAttribute("data-profile-role"));
      });
    });
  }

  window.refreshSidebarProfileCards = function (profile) {
    var nextProfile = profile && typeof profile === "object" ? syncProfileStorage(profile) : getStoredProfile();
    Array.prototype.forEach.call(document.querySelectorAll("[data-sidebar-profile-card]"), function (card) {
      updateProfileCard(card, nextProfile, card.getAttribute("data-profile-role"));
    });
  };

  whenReady(initSidebarProfiles);
})();
