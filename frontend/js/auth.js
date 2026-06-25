// ── Inicialización: detectar modo auth y callback SSO ────────────────────────
(async()=>{
  // 1. ¿Viene de callback Zitadel? (?token=...&user=...)
  const params=new URLSearchParams(window.location.search);
  if(params.has("token")){
    TOKEN=params.get("token");
    try{ USER=JSON.parse(params.get("user")||"{}"); }catch(e){ USER={}; }
    // Limpiar URL sin recargar
    history.replaceState({},"",window.location.pathname);
    if(TOKEN && USER.id){ enterApp(); return; }
  }
  // 2. Consultar modo auth al backend
  try{
    const cfg=await(await fetch(API+"/api/auth/config")).json();
    if(cfg.mode==="zitadel"){
      $("formLogin").classList.add("hidden");
      $("formRegister").classList.add("hidden");
      $("formSSO").classList.remove("hidden");
    }
  }catch(e){ /* sin conexión: mostrar login local */ }

  initNetworkAnimation();
  initDragAndDrop();
})();

function doSSOLogin(){
  const redirect=window.location.origin+window.location.pathname;
  window.location.href=`${API}/api/auth/zitadel/login?redirect=${encodeURIComponent(redirect)}`;
}

let captchaVerified = { login: false, register: false };

function showRegister(){
  $("formLogin").classList.add("hidden");
  $("formRegister").classList.remove("hidden");
  $("loginErr").textContent="";
  captchaVerified.register = false;
  const cb = document.querySelector("#registerCaptchaContainer .captcha-checkbox");
  if (cb) cb.className = "captcha-checkbox";
}

function showLogin(){
  $("formRegister").classList.add("hidden");
  $("formLogin").classList.remove("hidden");
  $("registerErr").textContent="";
  captchaVerified.login = false;
  const cb = document.querySelector("#loginCaptchaContainer .captcha-checkbox");
  if (cb) cb.className = "captcha-checkbox";
}

function togglePasswordVisibility(id, btn) {
  const input = document.getElementById(id);
  if (!input) return;
  const isPass = input.type === "password";
  input.type = isPass ? "text" : "password";
  btn.innerHTML = isPass
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}

function triggerCaptcha(box, type) {
  if (captchaVerified[type]) return;
  box.className = "captcha-checkbox loading";
  setTimeout(() => {
    box.className = "captcha-checkbox checked";
    captchaVerified[type] = true;
  }, 1100);
}

// ── Animación del Canvas (Red de Salud y Tecnología) ──────────────────
function initNetworkAnimation() {
  const canvas = document.getElementById("networkCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let width = canvas.width = canvas.offsetWidth;
  let height = canvas.height = canvas.offsetHeight;

  window.addEventListener("resize", () => {
    width = canvas.width = canvas.offsetWidth;
    height = canvas.height = canvas.offsetHeight;
  });

  const particles = [];
  const particleCount = 60;
  const maxDistance = 110;

  class Particle {
    constructor() {
      this.x = Math.random() * width;
      this.y = Math.random() * height;
      this.vx = (Math.random() - 0.5) * 0.4;
      this.vy = (Math.random() - 0.5) * 0.4;
      this.radius = Math.random() * 2 + 1.5;
      this.isCross = Math.random() < 0.12; // 12% cruces médicas
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;

      if (this.x < 0 || this.x > width) this.vx *= -1;
      if (this.y < 0 || this.y > height) this.vy *= -1;
    }

    draw() {
      if (this.isCross) {
        ctx.fillStyle = "rgba(111, 163, 232, 0.4)";
        ctx.font = "14px Inter, system-ui, sans-serif";
        ctx.fillText("+", this.x - 4, this.y + 4);
      } else {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(59, 120, 214, 0.35)";
        ctx.fill();

        if (this.radius > 2.5) {
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.radius * 2, 0, Math.PI * 2);
          ctx.fillStyle = "rgba(111, 163, 232, 0.08)";
          ctx.fill();
        }
      }
    }
  }

  for (let i = 0; i < particleCount; i++) {
    particles.push(new Particle());
  }

  let mouse = { x: null, y: null };
  const brandDiv = document.querySelector(".brand");
  if (brandDiv) {
    brandDiv.addEventListener("mousemove", (e) => {
      const rect = brandDiv.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    });
    brandDiv.addEventListener("mouseleave", () => {
      mouse.x = null;
      mouse.y = null;
    });
  }

  function animate() {
    ctx.clearRect(0, 0, width, height);

    for (let i = 0; i < particleCount; i++) {
      const p1 = particles[i];
      for (let j = i + 1; j < particleCount; j++) {
        const p2 = particles[j];
        const dx = p1.x - p2.x;
        const dy = p1.y - p2.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist < maxDistance) {
          const alpha = (1 - dist / maxDistance) * 0.15;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(111, 163, 232, ${alpha})`;
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      }

      if (mouse.x !== null && mouse.y !== null) {
        const dx = p1.x - mouse.x;
        const dy = p1.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < maxDistance + 30) {
          const alpha = (1 - dist / (maxDistance + 30)) * 0.22;
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(mouse.x, mouse.y);
          ctx.strokeStyle = `rgba(59, 120, 214, ${alpha})`;
          ctx.lineWidth = 1.0;
          ctx.stroke();
        }
      }
    }

    for (let i = 0; i < particleCount; i++) {
      particles[i].update();
      particles[i].draw();
    }

    requestAnimationFrame(animate);
  }

  animate();
}

function initDragAndDrop() {
  const dz = document.querySelector(".dz");
  if (!dz) return;

  // Prevenir comportamiento por defecto
  ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    dz.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
    }, false);
  });

  // Clases visuales al arrastrar
  ['dragenter', 'dragover'].forEach(eventName => {
    dz.addEventListener(eventName, () => dz.classList.add('dz-dragover'), false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dz.addEventListener(eventName, () => dz.classList.remove('dz-dragover'), false);
  });

  // Procesar archivo soltado
  dz.addEventListener('drop', e => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length) {
      const fileInput = $("file");
      if (fileInput) {
        fileInput.files = files;
        uploadFile(fileInput);
      }
    }
  }, false);
}

async function doLogin(){
  $("loginErr").textContent="";
  if (!captchaVerified.login) {
    $("loginErr").textContent = "Por favor, verifica que no eres un robot";
    const container = $("loginCaptchaContainer");
    container.style.borderColor = "var(--danger)";
    setTimeout(() => { container.style.borderColor = ""; }, 2000);
    return;
  }
  const body=new URLSearchParams({username:$("email").value,password:$("pass").value});
  try{
    const r=await fetch(API+"/api/auth/login",{method:"POST",body});
    if(!r.ok){$("loginErr").textContent="Correo o contraseña incorrectos";return;}
    const d=await r.json(); TOKEN=d.access_token; USER=d.user;
    enterApp();
  }catch(e){$("loginErr").textContent="No se pudo conectar con el servidor";}
}

async function doRegister(){
  $("registerErr").textContent="";
  const name=$("regName").value.trim(), email=$("regEmail").value.trim();
  const org=$("regOrg").value.trim(), pass=$("regPass").value;
  if(!name||!email||!pass){$("registerErr").textContent="Completa todos los campos";return;}
  if(pass.length<6){$("registerErr").textContent="La contraseña debe tener al menos 6 caracteres";return;}
  if (!captchaVerified.register) {
    $("registerErr").textContent = "Por favor, verifica que no eres un robot";
    const container = $("registerCaptchaContainer");
    container.style.borderColor = "var(--danger)";
    setTimeout(() => { container.style.borderColor = ""; }, 2000);
    return;
  }
  try{
    const r=await fetch(API+"/api/auth/register",{method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({name,email,password:pass,org_name:org||name})});
    if(!r.ok){const e=await r.json();$("registerErr").textContent=e.detail||"Error al crear cuenta";return;}
    const d=await r.json(); TOKEN=d.access_token; USER=d.user;
    enterApp();
  }catch(e){$("registerErr").textContent="No se pudo conectar con el servidor";}
}

async function enterApp(){
  $("login").classList.add("hidden"); $("app").classList.remove("hidden");
  $("userName").textContent=USER.name; $("hello").textContent="Hola, "+USER.name.split(" ")[0]+" 👋";
  const avatarInitials=USER.name.split(" ").map(s=>s[0]).join("").slice(0,2).toUpperCase();
  $("userAvatar").textContent=avatarInitials;

  // Rellenar la tarjeta del perfil del sidebar
  if($("sideUserName")) $("sideUserName").textContent=USER.name;
  if($("sideUserEmail")) $("sideUserEmail").textContent=USER.email||"";
  if($("sideUserAvatar")) $("sideUserAvatar").textContent=avatarInitials;

  const me=await(await fetch(API+"/api/auth/me",{headers:H()})).json();
  const orgName=me.org_name||USER.org_name||"Mi organización";
  $("orgName").textContent=orgName;
  USER.org_name=orgName;
  // Avatar de organización: primeras 2 letras
  const orgInitials=orgName.split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase();
  if($("orgAvatar")) $("orgAvatar").textContent=orgInitials;
  TEMPLATES=await(await fetch(API+"/api/templates",{headers:H()})).json();
  renderTemplates(); loadDashboard();
}

function logout(){TOKEN=null;USER=null;$("app").classList.add("hidden");$("login").classList.remove("hidden");}
