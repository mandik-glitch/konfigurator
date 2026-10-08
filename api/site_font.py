"""
site_font.py - vyber pisma pro CELY web (--font-main), self-service pro
admina.

Robert primo, 2026-09-17: "premyslim o nejakem jinem pismu napríc vebem,
idealne by bylo kdyz mi das adminovsky nejaky posuvnik na vyber vhodneho
pisma zive by se měnil... pismo nejake se slabsimi linkami", pak "je
vsude, proto to musim rozseknout dokud je web maly" - font-family byl
hardcoded (-apple-system,"Segoe UI",Roboto,Arial,sans-serif) na ~25
mistech napric webem (viz --font-main pouziti v kazde webapp/*.html) -
nahrazeno jednou sdilenou promennou s fallbackem na PUVODNI vzhled, presne
stejny vzor jako uz cat_tree_colors.py/pd_desc_opacity.py.

OMEZENA mnozina (whitelist klicu, ne volny text CSS) - i kdyz je vstup
jen od overeneho admina, syrovy retezec by se vkladal primo do <style>
tagu na KAZDE strance (viz site_font_ssr_head nize) a chyba/preklep by
rozbila cely web. Predem vybrane fonty maji navic zarucenou ceskou
diakritiku a rozumnou skalu vah (Light/Regular/Medium).

Monospace "HUD" pismo (SF Mono/Cascadia Code, .cat-tree-group-label,
.sidebar-title apod.) NENI soucasti teto volby - je to zamerny
"rysovaci prkno" vzhled (Robert 2026-08-09), --font-main resi jen hlavni
citelny text.
"""
from flask import jsonify, request

from app import app, get_conn, admin_required, current_user, log_audit, get_setting

# bot16, 2026-09-17 - kazda volba: theme-appropriate "slabsimi linkami"
# (Robert) sans-serif s Light/Regular vahou, dobra ceska diakritika,
# dostupne na Google Fonts (jedina externi zavislost - viz google klic).
# "system" = puvodni vzhled beze zmeny (fallback/vychozi, zadny externi
# font, zadny dalsi HTTP request navic).
FONT_OPTIONS = {
    "system": {
        "label": "Výchozí (systémové písmo)",
        "stack": '-apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": None,
    },
    "inter": {
        "label": "Inter",
        "stack": '"Inter", -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": "Inter:wght@300;400;500;600;700",
    },
    "plex": {
        "label": "IBM Plex Sans",
        "stack": '"IBM Plex Sans", -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": "IBM+Plex+Sans:wght@300;400;500;600",
    },
    "manrope": {
        "label": "Manrope",
        "stack": '"Manrope", -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": "Manrope:wght@300;400;500;600;700",
    },
    "outfit": {
        "label": "Outfit",
        "stack": '"Outfit", -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": "Outfit:wght@300;400;500;600",
    },
    "jakarta": {
        "label": "Plus Jakarta Sans",
        "stack": '"Plus Jakarta Sans", -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
        "google": "Plus+Jakarta+Sans:wght@300;400;500;600",
    },
}

SETTING_KEY = "site_font_key"
DEFAULT_KEY = "system"


def _resolve_key(raw):
    return raw if raw in FONT_OPTIONS else DEFAULT_KEY


@app.get("/api/public/site-font")
def public_site_font():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            key = _resolve_key(get_setting(cur, SETTING_KEY))
    finally:
        conn.close()
    # stack/google jsou verejne neskodne (nejsou to tajemstvi) - admin
    # widget (viz site_font_ssr_head nize) je potrebuje pro OKAMZITY
    # nahled bez reloadu stranky (Robert: "zive by se menilo").
    return jsonify({
        "key": key,
        "options": [
            {"key": k, "label": v["label"], "stack": v["stack"], "google": v["google"]}
            for k, v in FONT_OPTIONS.items()
        ],
    })


@app.put("/api/admin/site-font")
@admin_required
def admin_set_site_font():
    body = request.get_json(silent=True) or {}
    key = body.get("key")
    if key not in FONT_OPTIONS:
        return jsonify({"error": f"Neznámé písmo: {key}"}), 400
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_settings (setting_key, setting_value) VALUES (%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=%s",
                (SETTING_KEY, key, key),
            )
        conn.commit()
    finally:
        conn.close()
    log_audit(current_user()["id"], "update", "site_font", None, f"key={key}")
    return jsonify({"status": "ok", "key": key})


_ADMIN_WIDGET_JS = """
<script>
(function(){
  fetch("/api/auth/me").then(function(r){return r.ok?r.json():{user:null};}).then(function(d){
    if(!d.user || d.user.role!=="admin") return;
    // bot16, 2026-09-17 - jeden spolecny plovouci box na "vzhled webu"
    // (puvodne jen pismo, Robert pak primo: "chci regulovat i tu
    // zakladní černou barvu na vsech mistech" - pridano jako druhy radek
    // do TEHOZ boxu, at nevznika druhy nezavisly widget navic).
    var box=document.createElement("div");
    box.id="siteAppearanceAdminWidget";
    box.style.cssText="position:fixed;bottom:12px;right:12px;z-index:99999;background:rgba(20,20,26,.94);border:1px dashed #ff7a3d;border-radius:6px;padding:6px 10px;font:11px -apple-system,sans-serif;color:#ccc;display:flex;flex-direction:column;gap:5px;";
    document.body.appendChild(box);

    fetch("/api/public/site-font").then(function(r){return r.json();}).then(function(state){
      var row=document.createElement("div");
      row.style.cssText="display:flex;align-items:center;gap:6px;";
      var label=document.createElement("span");
      label.textContent="Admin: písmo webu";
      var select=document.createElement("select");
      select.style.cssText="font-size:11px;max-width:160px;";
      state.options.forEach(function(o){
        var opt=document.createElement("option");
        opt.value=o.key; opt.textContent=o.label;
        if(o.key===state.key) opt.selected=true;
        select.appendChild(opt);
      });
      // bot16, 2026-09-17 (Robert: "zive by se menilo") - OKAMZITY nahled
      // bez reloadu: dynamicky <link> na Google Fonts (jen kdyz jeste
      // neni na strance) + primo --font-main, ulozeni na server bezi na
      // pozadi. Dalsi navstevnici (a tahle stranka po pristim SSR
      // vykresleni) dostanou stejnou volbu uz z serveru (site_font_ssr_head).
      select.addEventListener("change", function(){
        var picked=null;
        state.options.forEach(function(o){ if(o.key===select.value) picked=o; });
        if(!picked) return;
        if(picked.google){
          var linkId="siteFontGoogleLink-"+picked.key;
          if(!document.getElementById(linkId)){
            var link=document.createElement("link");
            link.id=linkId; link.rel="stylesheet";
            link.href="https://fonts.googleapis.com/css2?family="+picked.google+"&display=swap";
            document.head.appendChild(link);
          }
        }
        document.documentElement.style.setProperty("--font-main", picked.stack);
        fetch("/api/admin/site-font", {
          method:"PUT", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({key:picked.key}),
        }).catch(function(){});
      });
      row.appendChild(label); row.appendChild(select);
      box.appendChild(row);
    }).catch(function(){});

    fetch("/api/public/base-dark-color").then(function(r){return r.json();}).then(function(state){
      var row=document.createElement("div");
      row.style.cssText="display:flex;align-items:center;gap:6px;";
      var label=document.createElement("span");
      label.textContent="Základní černá";
      var input=document.createElement("input");
      input.type="color";
      input.value=state.hex||state.default;
      input.style.cssText="width:26px;height:20px;padding:0;border:1px solid #555;border-radius:4px;cursor:pointer;background:none;";
      input.addEventListener("input", function(){
        document.documentElement.style.setProperty("--base-dark", input.value);
        fetch("/api/admin/base-dark-color", {
          method:"PUT", headers:{"Content-Type":"application/json"},
          body:JSON.stringify({hex:input.value}),
        }).catch(function(){});
      });
      row.appendChild(label); row.appendChild(input);
      box.appendChild(row);
    }).catch(function(){});
  }).catch(function(){});
})();
</script>
"""


def site_font_ssr_head(cur):
    # bot16, 2026-09-17 - volano z _render_og_page() (app.py) na KAZDE
    # strance, stejny vzor jako cat_tree_colors_ssr_style() - font je
    # pritomny uz v prvni HTML odpovedi ze serveru (--font-main + pripadny
    # Google Fonts <link>), zadny "problik" puvodni->nove pismo po
    # doběhnutí JS. system (vychozi) nepridava zadny externi pozadavek.
    # Admin widget (viz _ADMIN_WIDGET_JS) je soucasti stejneho vystupu,
    # at se objevi na KAZDE strance (Robert: "je vsude") bez nutnosti
    # rucne upravovat vsech ~25 souboru webapp/*.html jednotlive.
    key = _resolve_key(get_setting(cur, SETTING_KEY))
    opt = FONT_OPTIONS[key]
    html = ""
    if opt["google"]:
        html += (
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={opt["google"]}&display=swap">'
        )
    html += f'<style id="siteFontSSR">:root{{--font-main:{opt["stack"]}}}</style>'
    html += _ADMIN_WIDGET_JS
    return html
