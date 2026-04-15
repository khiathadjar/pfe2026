const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "http://127.0.0.1:8000";

document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = document.getElementById("loginEmail").value;
    const password = document.getElementById("loginPassword").value;

    try {
    const res = await fetch(`${API_BASE}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password })
        });

        const data = await res.json();

        if (res.ok) {
            // 1. On stocke le rôle et le token pour les utiliser plus tard
            localStorage.setItem("userRole", data.role);
            localStorage.setItem("userToken", data.access_token);
            localStorage.setItem("userEmail", data.email);
            localStorage.setItem("userId", data.user_id || "");
            if (data.display_name) {
                localStorage.setItem("userDisplayName", data.display_name);
                if (data.user_id) {
                    localStorage.setItem(`userDisplayName:${data.user_id}`, data.display_name);
                }
            } else {
                localStorage.removeItem("userDisplayName");
            }

            // 2. REDIRECTION LOGIQUE
            // Si c'est un admin -> index.html (Gestion complète)
            // Sinon (user) -> user.html
            if (data.role === "admin") {
                window.location.href = "index.html"; 
            } else {
                window.location.href = "user.html"; 
            }

        } else {
            alert("Erreur : " + (data.detail || "Identifiants invalides"));
        }
    } catch (error) {
        console.error("Erreur réseau :", error);
        alert("Impossible de contacter le serveur.");
    }
});
