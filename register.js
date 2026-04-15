const API_BASE = (window.APP_CONFIG && window.APP_CONFIG.API_BASE) || "http://127.0.0.1:8000";

document.getElementById("registerForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const email = document.getElementById("registerEmail").value;
  const password = document.getElementById("registerPassword").value;
  const confirm = document.getElementById("registerConfirm").value;

  if (password !== confirm) {
    alert("Les mots de passe ne correspondent pas ");
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok) {
      alert("Compte cree avec succes");
      window.location.href = "login.html";
    } else {
      alert(data.detail || "Erreur lors de l'inscription");
      console.log(data);
    }
  } catch (error) {
    console.error("Erreur reseau:", error);
    alert("Impossible de contacter le serveur.");
  }
});
