// App autonome MétéoVilles.
// - Au chargement : scrape toutes les villes (/api/refresh), grille injectée
//   dans un iframe srcdoc (JS des modales horaires isolé).
// - Ajout d'une ville via URL Météociel -> /api/cities/add -> re-scrap.
// - Suppression d'une ville (bouton ❌ sur chaque ligne) -> /api/cities/remove -> re-scrap.

var host = document.getElementById('grid-host');
var msgEl = document.getElementById('msg');

function showMsg(text, kind) {
  if (!text) { msgEl.hidden = true; return; }
  msgEl.textContent = text;
  msgEl.className = 'msg ' + (kind || '');
  msgEl.hidden = false;
}

function showLoading() {
  host.innerHTML = '<div class="loading"><span class="spinner"></span>' +
    '<p>Téléchargement des prévisions…</p></div>';
}

function injectGrid(fullHtml) {
  // La grille vit dans un iframe srcdoc : son CSS + le JS des modales horaires
  // s'exécutent de façon isolée, sans interférer avec l'app shell.
  host.innerHTML = '<iframe id="grid-frame"></iframe>';
  var frame = document.getElementById('grid-frame');
  frame.setAttribute('srcdoc', fullHtml);
}

async function refresh() {
  showLoading();
  showMsg('');
  try {
    var r = await fetch('/api/refresh', { method: 'POST' });
    var d = await r.json();
    if (d.ok && d.full) {
      injectGrid(d.full);
    } else {
      showMsg(d.error || 'Erreur lors du téléchargement.', 'error');
      host.innerHTML = '';
    }
  } catch (e) {
    showMsg('Erreur réseau : ' + e, 'error');
  }
}

async function addCity() {
  var input = document.getElementById('city-url');
  var url = input.value.trim();
  if (!url) return;
  showMsg('');
  try {
    var r = await fetch('/api/cities/add', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    var d = await r.json();
    if (d.ok) {
      input.value = '';
      showMsg('✅ ' + d.city.name + ' ajoutée. Téléchargement…', 'ok');
      refresh();
    } else {
      showMsg(d.error, 'error');
    }
  } catch (e) {
    showMsg('Erreur : ' + e, 'error');
  }
}

// Suppression d'une ville : le bouton ❌ est injecté dans la grille (iframe),
// on communique via postMessage de l'iframe vers le parent.
window.addEventListener('message', function (ev) {
  var data = ev.data;
  if (!data || data.source !== 'meteo') return;
  if (data.action === 'remove' && data.slug) {
    if (!confirm('Supprimer ' + (data.name || data.slug) + ' de ta liste ?')) return;
    removeCity(data.slug);
  }
});

async function removeCity(slug) {
  try {
    var r = await fetch('/api/cities/remove', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: slug })
    });
    var d = await r.json();
    if (d.ok) {
      showMsg('🗑️ Ville supprimée. Actualisation…', 'ok');
      refresh();
    } else {
      showMsg(d.error || 'Erreur suppression', 'error');
    }
  } catch (e) {
    showMsg('Erreur : ' + e, 'error');
  }
}

document.getElementById('btn-add').addEventListener('click', addCity);
document.getElementById('btn-refresh').addEventListener('click', refresh);
document.getElementById('city-url').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') addCity();
});

// Modale d'aide
var helpOverlay = document.getElementById('help-overlay');
document.getElementById('btn-help').addEventListener('click', function () {
  helpOverlay.hidden = false;
});
document.getElementById('help-close').addEventListener('click', function () {
  helpOverlay.hidden = true;
});
helpOverlay.addEventListener('click', function (e) {
  if (e.target === helpOverlay) helpOverlay.hidden = true;
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' && !helpOverlay.hidden) helpOverlay.hidden = true;
});

// Démarrage : scrape tout (zéro cache)
refresh();
