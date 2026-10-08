"""E-shop stránky (SSR) a SEO: veřejné product.html/produkt/<slug>,
category.html/kategorie/<slug>, "/"+index.html, blok/<slug>, panel/<slug>,
robots.txt, sitemap.xml.

Vyčleněno z api/app.py (PLAN_ROZDELENI_BACKENDU.md skupina 13) - čistý
přesun, žádná změna chování/URL. Řada helperů (_render_og_page,
_get_og_site_defaults, _og_escape, _ld_json_script, FAQ helpery,
_build_category_tree, _category_tree_show_hidden,
_category_products_with_images...) zůstává v app.py, protože je používá
i kód mimo tuhle skupinu (SEO rendering homepage-bloků/panelů - plán
skupina 2, kategorie admin API - plán skupina 14) - modul si je jen
importuje.
"""
import datetime
import json
import os
import re
import sys
from urllib.parse import quote

from flask import request, redirect, Response

from products import _is_staff_request
from app import (
    app, get_conn, PUBLIC_BASE_URL,
    _render_og_page, _get_og_site_defaults, _og_escape, _ld_json_script,
    _extract_faq_pairs, _faq_page_ld, _strip_empty_faq_block,
    _build_category_tree, _category_tree_show_hidden,
    _category_products_with_images, _category_representative_image_url,
    get_setting,
    _render_homepage_mosaic_html, _render_announcement_preview_html,
    _render_homepage_carousel_html,
    _content_file_dimensions,
)


# bot16, 2026-09-17 (Robert schvalil pres bot7 artifact, "aplikovat" HNED) -
# znackova loga pro podkategorie-dlazdice pod "Vestavby podle vozidla" (id
# 267). Simple Icons (CC0-1.0, simpleicons.org) - male rozpoznavaci logo v
# kontextu "vestavba pro tuhle znacku", ne oficialni brand asset (bezna
# aftermarket praxe, tak i formulovano ve schvalenem mockupu). Inline SVG
# (ne <img src>) zamerne - jen tak jde barvu resit cistě CSS (fill), bez
# druheho HTTP requestu na sotva pouzitelny raster/filter trik.
# Klic = content_categories.id konkretni znackove podkategorie (napevno,
# jsou jen tyhle 4/6 - zadny novy DB sloupec pro jednorazovy seznam).
# DRZET SYNCHRONNI s BRAND_LOGOS v category.html (renderSubcats()) -
# stejna konvence jako uz existujici "cs-media, drzet obe verze
# synchronni" nize.
BRAND_LOGOS = {
    268: '<path d="M12 0C6.684 0 2.292 5.38 2.292 12S6.652 24 12 24c5.347 0 9.708-5.38 9.708-12S17.316 0 12 0zM4.106 16.233c-.19-.604-.35-1.241-.414-1.878L12 8.18l8.371 6.175a12.334 12.334 0 0 1-.413 1.878v.032h-.032L12 10.345zm.923 2.101-.032-.032L12 13.114l7.003 5.188v.032c-1.655 2.897-4.202 4.616-6.987 4.616s-5.363-1.751-6.987-4.616zM12 5.347l-8.53 6.335v-.032c.063-2.674.954-5.284 2.61-7.385C7.67 2.324 9.772 1.21 12 1.21c2.228 0 4.36 1.114 5.92 3.055 1.56 1.942 2.515 4.616 2.61 7.417v.032l-.031-.032z"/>',  # Citroën
    269: '<path d="M21.175 6.25c.489 1.148.726 2.442.726 3.956 0 .818-.068 1.69-.206 2.666-.286 2.01-1.048 4.11-1.75 5.494-.114.223-.205.371-.388.533-.32.282-.602.352-.706.291-.084-.05-.131-.302-.114-.673.014-.316.089-.55.204-.924a36.261 36.261 0 0 0 1.2-5.416c.385-2.664.37-5.06-.201-6.52a2.224 2.224 0 0 0-.22-.427c-.062-.09-.106-.136-.106-.136-1.181-1.183-4.37-1.776-7.56-1.776-3.19 0-6.378.593-7.558 1.776 0 0-.045.045-.106.136a2.122 2.122 0 0 0-.221.426c-.572 1.46-.586 3.857-.201 6.521.26 1.807.672 3.72 1.227 5.504.096.307.158.516.173.84.016.369-.03.62-.114.67-.104.06-.389-.01-.71-.295-.23-.205-.345-.405-.49-.701-.68-1.385-1.393-3.397-1.667-5.323a18.884 18.884 0 0 1-.206-2.666c0-1.514.238-2.807.726-3.954.367-.86.983-1.58 1.782-2.083a13.892 13.892 0 0 1 6.526-2.122 13.9 13.9 0 0 1 .815-.026h.02c.274 0 .548.01.818.026 2.282.138 4.539.873 6.525 2.122a4.583 4.583 0 0 1 1.782 2.082zm-4.763 14.526c-.088.019-.361.083-.632.157-.243.067-.483.12-.597.143a16.51 16.51 0 0 1-3.115.285h-.028c-1.117 0-2.177-.103-3.114-.285a9.23 9.23 0 0 1-.56-.133 14.987 14.987 0 0 0-.604-.148c-.418-.095-.796-.163-.817-.083-.025.093.162.288.401.472.056.042.195.14.357.22.15.073.32.128.386.15 1.098.355 2.346.502 3.941.502h.022c1.563 0 2.794-.142 3.877-.483.371-.117.59-.211.853-.42.22-.174.385-.353.361-.44-.02-.075-.348-.021-.731.063zm-2.508-10.313c-.145-.81-.32-1.432-.518-1.85l-.002-.004h-.021l-.682-.006h-.01l-.027 2.998h1.426l-.001-.01c0-.005-.056-.522-.165-1.128zm5.76 1.687c-.322 2.228-.88 4.623-1.66 6.701-.13.35-.248.48-.53.7a6.23 6.23 0 0 1-2.431 1.028c-.897.175-1.908.272-2.974.272h-.029a15.66 15.66 0 0 1-2.973-.272 6.23 6.23 0 0 1-2.433-1.028c-.282-.22-.399-.35-.527-.7-.782-2.078-1.34-4.473-1.661-6.701-.373-2.577-.35-4.847.18-6.202.067-.17.138-.292.19-.369.046-.065.078-.1.078-.1 1.068-1.07 4.06-1.652 7.16-1.652 3.101 0 6.093.582 7.16 1.653 0 0 .032.033.078.1.052.076.124.197.19.368.531 1.355.554 3.625.182 6.202zM8.904 7.565L6.222 7.55l.267 9.337 1.122.012-.016-4.25h1.014v-1.097H7.595V8.66h1.31V7.564zm1.876-.02l-1.365.003.181 9.35h1.157l.027-9.352zm3.448.014h-2.732l.108 9.334h1.092l.009-4.222h1.418l.002.007c.128.797.138 4.171.138 4.205v.015h1.063l.009-.479c.048-2.42.13-6.469-1.107-8.86zm4.32-.013l-3.344.013v1.077h.998v.01l-.042 8.252h1.132l.275-8.262h.981v-1.09zM23.975 12c0 6.617-5.372 12-11.976 12C5.397 24 .025 18.617.025 12S5.397 0 12 0c6.604 0 11.976 5.383 11.976 12zm-.33-.008C23.64 5.561 18.418.33 11.998.33 5.642.33.46 5.463.358 11.811a1.71 1.71 0 0 1 .684-.78c.655-.388.834-1.385.893-1.981l.012-.062c-.039.395-.07.79-.07 1.218 0 .832.07 1.718.21 2.708.412 2.9 1.813 6.007 2.637 6.958l.046.05.192.202.007.006c2.01 1.647 3.857 2.23 7.061 2.23h.022c3.203 0 5.05-.583 7.06-2.23l.009-.006.185-.197.052-.056c.826-.954 2.226-4.057 2.638-6.957.14-.99.209-1.876.209-2.708 0-.454-.021-.89-.064-1.309l.006.006c.06.597.379 2.141.995 2.586.21.152.375.317.503.503z"/>',  # Fiat
    270: '<path d="M12 0c6.623 0 12 5.377 12 12s-5.377 12-12 12S0 18.623 0 12 5.377 0 12 0zM3.245 17.539A10.357 10.357 0 0012 22.36c3.681 0 6.917-1.924 8.755-4.821L12 14.203zm10.663-6.641l7.267 5.915A10.306 10.306 0 0022.36 12c0-5.577-4.417-10.131-9.94-10.352zm-2.328-9.25C6.057 1.869 1.64 6.423 1.64 12c0 1.737.428 3.374 1.185 4.813l7.267-5.915z"/>',  # Mercedes
    271: '<path d="M12 0C5.36 0 0 5.36 0 12S5.36 24 12 24 24 18.64 24 12 18.64 0 12 0M12 1.41C13.2 1.41 14.36 1.63 15.43 2L12.13 9.13C12.09 9.17 12.09 9.26 12 9.26S11.91 9.17 11.87 9.13L8.57 2C9.64 1.63 10.8 1.42 12 1.42M6.9 2.74L10.72 10.97C10.8 11.14 10.89 11.19 11 11.19H13C13.12 11.19 13.2 11.14 13.29 10.97L17.06 2.74C18.64 3.64 20 4.93 20.96 6.47L15.6 16.84C15.56 16.93 15.5 16.97 15.47 16.97C15.39 16.97 15.39 16.89 15.34 16.84L13.29 12.3C13.2 12.13 13.12 12.09 13 12.09H11C10.89 12.09 10.8 12.13 10.71 12.3L8.66 16.84C8.61 16.89 8.62 16.97 8.53 16.97C8.44 16.97 8.44 16.89 8.4 16.84L3 6.47C3.94 4.93 5.32 3.64 6.9 2.74M2.06 8.53L8.23 20.53C8.31 20.7 8.4 20.83 8.62 20.83C8.83 20.83 8.91 20.7 9 20.53L11.87 14.14C11.91 14.06 11.96 14 12 14C12.09 14 12.09 14.1 12.13 14.14L15.04 20.53C15.13 20.7 15.21 20.83 15.43 20.83C15.64 20.83 15.73 20.7 15.81 20.53L22 8.53C22.37 9.6 22.59 10.76 22.59 12C22.54 17.79 17.79 22.59 12 22.59C6.21 22.59 1.46 17.79 1.46 12C1.46 10.8 1.67 9.65 2.06 8.53Z"/>',  # Volkswagen
    279: '<path d="M12 8.236C5.872 8.236.905 9.93.905 12.002S5.872 15.767 12 15.767c6.127 0 11.094-1.693 11.094-3.765 0-2.073-4.967-3.766-11.094-3.766zm-5.698 6.24c-.656.005-1.233-.4-1.3-1.101a1.415 1.415 0 0 1 .294-1.02c.195-.254.525-.465.804-.517.09-.017.213-.006.264.054.079.093.056.194-.023.234-.213.109-.47.295-.597.55a.675.675 0 0 0 .034.696c.263.397.997.408 1.679-.225.169-.156.32-.304.473-.48.3-.344.4-.47.8-1.024.005-.006.006-.014.004-.018-.003-.007-.009-.01-.02-.01-.267.007-.5.087-.725.255-.065.048-.159.041-.2-.021-.046-.07-.013-.163.062-.215.363-.253.76-.298 1.166-.367 0 0 .028.002.051-.03.167-.213.292-.405.47-.621.178-.22.41-.42.586-.572.246-.212.404-.283.564-.37.043-.022-.005-.049-.018-.049-.896-.168-1.827-.386-2.717-.056-.616.23-.887.718-.757 1.045.093.231.397.27.683.13a1.55 1.55 0 0 0 .611-.544c.087-.134.27-.038.171.195-.26.611-.757 1.097-1.363 1.118-.516.016-.849-.363-.848-.831.002-.924 1.03-1.532 2.11-1.622 1.301-.108 2.533.239 3.825.395.989.12 1.938.123 2.932-.106.118-.025.2.05.193.168-.01.172-.143.337-.47.516-.373.204-.763.266-1.17.27-.984.008-1.901-.376-2.85-.582.002.041.012.091-.023.117-.525.388-1 .782-1.318 1.334-.011.013-.005.025.013.024.277-.015.525-.022.783-.042.045-.004.047-.015.043-.048a.64.64 0 0 1 .2-.558c.172-.153.387-.17.53-.06.16.126.147.353.058.523a.63.63 0 0 1-.382.31s-.03.006-.026.034c.006.043.2.151.217.18.017.027.008.07-.021.102a.123.123 0 0 1-.095.045c-.033 0-.053-.012-.096-.035a.92.92 0 0 1-.27-.217c-.024-.031-.037-.032-.099-.029-.279.017-.714.059-1.009.096-.071.008-.082.022-.096.047-.47.775-.972 1.61-1.523 2.17-.592.6-1.083.758-1.604.762zM19.05 10.71c-.091.158-1.849 2.834-1.96 3.11-.035.088-.04.155-.004.204.092.124.297.051.425-.038.381-.262.645-.58.937-.858.017-.013.046-.018.065 0 .043.04.106.091.15.137a.04.04 0 0 1 .002.057 5.873 5.873 0 0 1-.904.911c-.47.364-.939.457-1.172.224a.508.508 0 0 1-.14-.316c-.002-.057-.031-.06-.058-.034-.278.275-.76.579-1.198.362-.366-.18-.451-.618-.383-.986.001-.008-.006-.06-.051-.03a1.28 1.28 0 0 1-.3.162.853.853 0 0 1-.366.077.518.518 0 0 1-.451-.253.759.759 0 0 1-.095-.347c-.001-.011-.017-.032-.033-.005-.3.457-.579.899-.875 1.363-.016.022-.03.036-.06.037l-.587.001c-.036 0-.053-.028-.034-.063.104-.2.674-1.03 1.06-1.736.107-.194.085-.294.019-.337-.083-.054-.248.027-.387.133-.379.287-.697.735-.859.935-.095.117-.185.291-.433.56-.391.425-.91.669-1.408.5a.848.848 0 0 1-.546-.58c-.015-.052-.044-.066-.073-.032-.08.1-.245.249-.383.342-.015.011-.052.033-.084.017a.851.851 0 0 1-.152-.199.07.07 0 0 1 .016-.08c.197-.173.305-.271.391-.38.064-.08.113-.17.17-.315.12-.302.393-.866.938-1.158a1.81 1.81 0 0 1 .652-.219c.1-.01.183.002.213.08.011.033.039.105.056.158.011.032.003.057-.035.071-.32.122-.643.311-.865.61-.253.338-.321.746-.152.98.123.17.322.2.514.139.29-.092.538-.363.666-.663.138-.329.16-.717.058-1.059-.016-.059-.001-.104.037-.136.077-.063.184-.112.215-.128a.14.14 0 0 1 .182.045c.106.157.163.378.17.607.006.049.026.05.05.025.19-.202.366-.418.568-.58.185-.147.422-.267.643-.262.286.006.428.2.419.546-.001.044.03.04.051.011a1.19 1.19 0 0 1 .24-.264c.198-.163.4-.236.611-.222.26.02.468.257.425.527a.53.53 0 0 1-.281.406.362.362 0 0 1-.405-.044.336.336 0 0 1-.096-.322c.005-.025-.027-.048-.054-.02-.254.264-.273.606-.107.76.183.17.458.056.658-.075.366-.239.65-.563.979-.813.218-.166.467-.314.746-.351a.87.87 0 0 1 .454.052c.2.081.326.25.342.396.004.043.036.048.063.01.158-.246 1.005-1.517 1.075-1.65.02-.041.044-.047.089-.047h.606c.035 0 .051.02.036.047zm-2.32 2.204a.053.053 0 0 0-.003.04c.003.02.03.04.056.05.01.003.015.01.004.032-.075.16-.143.252-.237.391a1.472 1.472 0 0 1-.3.325c-.178.147-.424.307-.628.2-.09-.047-.13-.174-.127-.276.004-.288.132-.584.369-.875.288-.355.607-.539.816-.438.216.103.148.354.05.55zm-5.949-1.881a.398.398 0 0 1 .132-.345c.057-.05.133-.062.18-.022.052.045.027.157-.026.234a.43.43 0 0 1-.245.177c-.018.004-.034-.004-.041-.044zM12 7.5C5.34 7.5 0 9.497 0 12c0 2.488 5.383 4.5 12 4.5s12-2.02 12-4.5-5.383-4.5-12-4.5zm0 8.608C5.649 16.108.5 14.27.5 12.002.5 9.733 5.65 7.895 12 7.895s11.498 1.838 11.498 4.107c0 2.268-5.148 4.106-11.498 4.106z"/>',  # Ford
    281: '<path d="M12 3.848C5.223 3.848 0 7.298 0 12c0 4.702 5.224 8.152 12 8.152S24 16.702 24 12c0-4.702-5.223-8.152-12-8.152zm7.334 3.839c0 1.08-1.725 1.913-4.488 2.246-.26-2.58-1.005-4.279-1.963-4.913 2.948.184 6.45 1.227 6.45 2.667zM12 16.401c-.96 0-1.746-1.5-1.808-4.389.577.047 1.18.072 1.808.072.628 0 1.23-.025 1.807-.072-.061 2.89-.847 4.389-1.807 4.389zm0-6.308c-.59 0-1.155-.019-1.69-.054.261-1.728.92-3.15 1.69-3.15.77 0 1.428 1.422 1.689 3.15-.535.034-1.099.054-1.689.054zm-.882-5.075c-.956.633-1.706 2.333-1.964 4.915C6.391 9.6 4.665 8.767 4.665 7.687c0-1.44 3.504-2.49 6.453-2.669zM2.037 11.68a5.265 5.265 0 011.048-3.164c.27 1.547 2.522 2.881 5.972 3.37V12c0 3.772.879 6.203 2.087 6.97-5.107-.321-9.107-3.48-9.107-7.29zm10.823 7.29c1.207-.767 2.087-3.198 2.087-6.97v-.115c3.447-.488 5.704-1.826 5.972-3.37a5.26 5.26 0 011.049 3.165c-.004 3.81-4.008 6.969-9.109 7.29z"/>',  # Toyota
    285: '<path d="M17.463 11.99l-4.097-7.692-.924 1.707 3.213 5.985-5.483 10.283L4.69 11.99 11.096 0H9.27L2.882 11.99 9.269 24h1.807zm3.655 0L14.711 0h-1.807L6.517 11.99l4.117 7.712.904-1.707-3.193-6.005 5.463-10.263L19.29 11.99 12.904 24h1.807Z"/>',  # Renault
    286: '<path d="M12.291 4.57a7.46 7.46 0 0 0-7.338 5.006h.568a6.926 6.926 0 0 1 6.483-4.494 6.922 6.922 0 0 1 6.922 6.924c0 .116 0 .234-.01.351l.533.059c0-.134.01-.273.01-.4a7.46 7.46 0 0 0-7.168-7.446zM.869 10.113 0 10.566l13.25 1.44 3.63-1.893H.87zm3.682 1.483v.41a7.46 7.46 0 0 0 14.498 2.441h-.57a6.924 6.924 0 0 1-6.475 4.487 6.928 6.928 0 0 1-6.92-6.928v-.352l-.533-.058zm6.193.414-3.63 1.898h16.011l.873-.453v-.006l-13.254-1.44zm13.254 1.44H24l-.002-.007v.006z"/>',  # Opel
    287: '<path d="M.084 10.059a.084.084 0 0 0-.084.084v3.574c0 .046.038.084.084.084h.912a.083.083 0 0 0 .082-.084v-3.574a.083.083 0 0 0-.082-.084zm1.775 0c-.062 0-.105.058-.076.11l1.895 3.257.011.02c.195.306.577.495 1.002.494.426-.001.807-.196.997-.508L7.75 10.17c.028-.046-.007-.111-.076-.111H6.658a.086.086 0 0 0-.074.039l-1.857 2.925c-.017.028-.064.023-.079.006L2.936 10.1a.085.085 0 0 0-.077-.04zm7.598 0c-.73-.001-1.324.488-1.324 1.091v1.557c0 .603.594 1.094 1.324 1.094h3.049a.082.082 0 0 0 .082-.084v-.733a.082.082 0 0 0-.082-.084H9.234c-.017 0-.03-.015-.03-.033V10.99c0-.017.013-.033.03-.033h3.272a.08.08 0 0 0 .082-.082v-.732a.082.082 0 0 0-.082-.084zm5.443 0c-.73-.001-1.324.488-1.324 1.091v1.557c0 .603.594 1.094 1.324 1.094h3.05a.084.084 0 0 0 .083-.084v-.733a.084.084 0 0 0-.084-.084h-3.271c-.018 0-.032-.015-.032-.033V10.99c0-.017.014-.033.032-.033h3.271a.082.082 0 0 0 .084-.082v-.732a.084.084 0 0 0-.084-.084zm5.334 0c-.73 0-1.324.49-1.324 1.093v1.555c0 .603.594 1.094 1.324 1.094h2.442c.73 0 1.324-.49 1.324-1.094v-1.555c0-.603-.594-1.093-1.324-1.093zm-.226.898h2.879c.015 0 .027.012.027.027v1.889a.027.027 0 0 1-.027.027h-2.88a.027.027 0 0 1-.027-.027v-1.889c0-.015.013-.027.028-.027zm-10.215.56a.05.05 0 0 0-.049.051v.73c0 .028.022.052.049.052h2.72a.05.05 0 0 0 .05-.051v-.73a.05.05 0 0 0-.05-.051z"/>',  # Iveco
    288: '<path d="M12.0001 0c3.499 0 7.1308.2987 10.8171.9349.055 1.4778.1175 3.762.0126 5.7004-.2349 4.3217-1.1861 7.676-2.9943 10.5564-1.8026 2.872-4.5938 5.3416-7.8354 6.8083-3.2416-1.4667-6.0331-3.9362-7.8356-6.8083-1.808-2.8804-2.7594-6.2348-2.9941-10.5564-.1053-1.9383-.0427-4.2226.0124-5.7004C4.8691.2987 8.5011 0 12.0001 0zm0 .4163c-3.4494 0-6.9514.2933-10.4139.8722-.076 2.1923-.076 3.9367-.0005 5.3243.2305 4.248 1.1619 7.5394 2.9309 10.3575 1.7688 2.8179 4.421 5.1457 7.4835 6.5718 3.0622-1.4261 5.7147-3.7539 7.4835-6.5718 1.769-2.8182 2.7001-6.1095 2.9309-10.3575.0755-1.3876.0755-3.132-.0005-5.3243C18.9515.7096 15.4493.4163 12.0001.4163zM11.97 13.0361s.0681.4045.0888.5218c.0116.0665.0141.0843-.0027.1495-.0477.1695-.3633 1.59-.5385 2.6258-.0822.4767-.1533.9498-.1947 1.3546-.0234.23-.0158.2851.0449.4892.172.5767.8082 2.0834.9304 2.3581a.3288.3288 0 0 1 .0257.0951l.0459.3553c-.2038-.3081-1.3115-2.3458-1.7465-3.4742-.0513-.1329-.0612-.1984-.0044-.4428.3025-1.2962 1.1211-3.4992 1.3511-4.0324zm-1.6153-3.1317c.0312.0913.2909.9805.3107 1.1919.016.1174.0133.149-.0284.2614-.2276.606-.9159 2.1129-1.1814 2.6161-.059.1107-.1145.1828-.2256.2958-.2535.2582-.7386.7462-1.039 1.0192-.1091.0993-.1385.1841-.1607.3126-.0358.2063-.0713.5584-.0812.7402-.0086.1599.0173.2347.1064.3931.5294.9451 2.2966 3.1194 2.8001 3.576.0365.0331.0632.0553.1402.1065.074.0494.3154.2061.3154.2061a.085.085 0 0 1 .0239.0257l.0874.1539c-.2256-.1123-.5874-.2928-.7742-.3929a.7527.7527 0 0 1-.1249-.0845c-.5896-.4902-2.3963-2.6064-2.9277-3.49-.1325-.2206-.1461-.292-.1283-.5008.0333-.3887.0849-.8774.1301-1.0916.0274-.1292.0558-.2051.1547-.3192.7533-.8648 2.2059-2.7743 2.6293-3.5908.0471-.0924.0511-.1245.0521-.2117.0027-.253-.078-.7457-.0992-.8702a.2385.2385 0 0 1-.0025-.0591l.0228-.2877zm4.931-.4748c.0812.0377.2137.0801.2732.1502.9366.9784 1.6856 1.9929 1.8356 2.2603.0289.0514.0486.1028.0558.1616.1683 1.4269.0237 2.9385-.3201 4.2535-.0311.1186-.0659.1794-.1799.2651-.7607.5713-2.5689 2.0716-3.176 2.6297a.996.996 0 0 0-.1718.2088c-.153.2511-.3419.6012-.462.825-.1234-.2696-.3924-.9273-.4847-1.1931-.0301-.0867-.0355-.1322-.0037-.2483.1505-.5512.862-2.1538 1.0005-2.4436-.0018.0372.0063.1347-.0079.1693-.0624.1895-.445 1.4526-.5227 2.0003-.0173.1218-.0158.1547 0 .2743.0341.2557.1868.7247.1868.7247.0174-.0414.1887-.3836.309-.4774.7089-.6984 2.1971-1.9725 3.0499-2.6638.0958-.0776.1315-.1295.1528-.2767.1056-.7254.1362-2.0275.0726-2.9751a1.012 1.012 0 0 0-.1708-.5003c-.231-.3417-.5072-.6651-.926-1.0805a.4152.4152 0 0 1-.1157-.2187c-.1222-.6524-.3949-1.8453-.3949-1.8453zm-7.9201 1.5091a.3306.3306 0 0 1 .1794-.0067c.267.0642.8322.2029 1.2594.3123.06.0153.1347.0714.1666.1245l.093.1549a.1822.1822 0 0 1 .0059.1774 21.7947 21.7947 0 0 1-.3055.5651l-.0886.1583c-.1631.2896-.3254.5691-.4176.7161-.0607.0971-.0945.1401-.2026.1784-.4203.148-.9423.3249-1.2525.4255-.0634.0205-.0849.0591-.0726.1295.0222.1282.0938.5636.1212.6906.0101.0469.0476.0843.1172.0709.1834-.0348.6715-.1544.6715-.1544s-.1439.1332-.23.2117a.1456.1456 0 0 1-.0545.0324c-.133.0445-.4578.1356-.559.1579-.079.017-.1293-.0141-.1496-.1035 0 0-.1385-.59-.1885-.7907a1.552 1.552 0 0 0-.0254-.0872c-.0375-.1161-.1276-.3444-.1784-.464a.108.108 0 0 1-.0087-.044c.0015-.1366.0267-.4415.0267-.4415s.2989.2804.4435.3817c.0326.023.0521.0277.0921.0175.1987-.0511.6555-.2024.9062-.2962a.3475.3475 0 0 0 .1463-.1048c.2594-.3135.5846-.8013.7725-1.1692a.2194.2194 0 0 0 .0146-.1631l-.0405-.1334c-.0118-.039-.0531-.083-.0911-.0976a34.0249 34.0249 0 0 0-1.1999-.4329l.0489-.0155zm8.7416-3.7975a.407.407 0 0 1 .2994.0069c.7409.3113 1.9867 1.0437 2.6792 1.5596.0669.0499.0935.0843.1111.1648.1626.7402.2243 1.8845.1219 2.8478-.0074.0692-.0212.1107-.0573.1846-.4388.8981-.9326 1.7434-1.4524 2.3954.0078-.0807.0446-.4617.0471-.6834a.0765.0765 0 0 1 .0304-.0605 9.0576 9.0576 0 0 0 .304-.2468c.0365-.0316.0568-.0553.0758-.086.2117-.3425.5903-1.0595.7428-1.4909a.787.787 0 0 0 .0429-.3281c-.0489-.6011-.1431-1.434-.2836-1.9776a.3337.3337 0 0 0-.1703-.2147c-.1212-.0623-.3588-.1707-.9-.3879a.7631.7631 0 0 1-.2068-.1238c-.3549-.2985-.9097-.7459-1.2549-1.0034a.4301.4301 0 0 0-.3527-.0749 21.4993 21.4993 0 0 0-.7517.1856c-.0612.0166-.0854.018-.1486.0106-.1009-.0117-.3007-.0275-.382-.0336.5871-.2761 1.152-.5142 1.5057-.6437zM8.274 12.0001c-.1836.3024-.403.6236-.5689.8243a.1988.1988 0 0 1-.0834.0588 14.1489 14.1489 0 0 1-.7063.2382l1.3586-1.1213zm-2.4267-.397l-.1083.7484-.3685-.4329c.0671-.1455.2633-.2829.4768-.3155zm-.6866-1.6986l-.133.0838c-.0333.0212-.0424.0304-.0563.0595a2.6968 2.6968 0 0 1-.0856.1616c-.0091.0158-.0336.0403-.0466.0504a16.6112 16.6112 0 0 1-.4773.3533c-.0089.0062-.0202.0035-.0279-.004-.0165-.0166-.0859-.0954-.0982-.1139a.0823.0823 0 0 1-.0151-.0489 2.0329 2.0329 0 0 1 .0062-.1337c.0039-.0509.0185-.0751.0805-.1394.0693-.0719.1449-.1475.2243-.2251.1947-.1641.6863-.5633 1.5642-1.1904a.1927.1927 0 0 0 .0437-.0423c.0921-.1244.354-.4644.4186-.5452a.1928.1928 0 0 1 .0308-.0311 2.4849 2.4849 0 0 1 .2595-.1833c.2445-.1542.7181-.4354.9834-.5898l-.1007.124c-.0056.0055-.0111.0106-.0167.0163a42.2875 42.2875 0 0 0-.5625.4314c-.0286.0227-.04.0425-.0466.0783-.0227.1266-.0605.367-.0716.5001-.0032.039-.02.0583-.0597.0744-.173.0704-.3781.1445-.5439.211-.0356.0141-.0454.0195-.0664.0356-.0166.0128-.2369.2098-.2369.2098s.479-.1181.6547-.1579c.042-.0094.06-.0069.0987.0114.0363.0168.0967.0408.1286.0524.0489.018.0748.0172.1288.0054.1979-.0442.5308-.1233.708-.1695.0921-.024.1424-.0489.2204-.1035.0849-.0591.2999-.2205.2999-.2205s-.004.0285-.0069.0443a.0591.0591 0 0 1-.0161.0318 3.986 3.986 0 0 1-.1581.1777c-.0871.0902-.1392.1223-.2485.168-.5035.21-1.3638.5362-2.0091.7598-.0423.0148-.0606.0269-.0919.059-.0341.0346-.0795.085-.0795.085s.5262.0383.6868.0568c.0521.0059.0893.023.1291.0573.132.1137.5691.5641.6999.7205 0 0-1.2426.2068-1.8184.3499-.0711.0175-.1066.0628-.1227.1198-.0476.1675-.1599.7062-.1599.7062s-.04-.0128-.0958-.045c-.0383-.022-.0577-.0403-.0997-.0847-.1362-.144-.3601-.4198-.4677-.5796-.0316-.0472-.0449-.1072-.0054-.1554.1167-.1438.3512-.4062.4805-.5411.0138-.0146.0313-.04.0499-.0766.0498-.1032.1038-.3175.1282-.4139zm8.0217-2.8166a.1805.1805 0 0 1 .1083.0148l.2564.1228a.0935.0935 0 0 1 .0503.0628c.0348.1468.0775.3412.1061.5065a.2993.2993 0 0 1-.036.1994c-.1061.1846-.324.5166-.446.695-.0271.04-.0304.0885-.022.1361.0553.3059.2858 1.374.2858 1.374l-.1451-.1322a.2102.2102 0 0 1-.0602-.0917c-.1032-.3022-.2962-.9335-.385-1.2406a.1588.1588 0 0 1 .0299-.145c.1513-.1838.3717-.4778.5005-.6641.036-.0524.0479-.1102.0267-.1534a4.6142 4.6142 0 0 0-.1273-.2369.1058.1058 0 0 0-.0597-.0489l-.174-.0558a.1452.1452 0 0 0-.093.0017c-.3791.1376-.8889.336-1.2009.4655-.0457.019-.0644.0205-.1197.0121-.0903-.0133-.3534-.0605-.4825-.0847a.0344.0344 0 0 1-.023-.0511l.153-.2654a.1474.1474 0 0 1 .0955-.0704c.4922-.1123 1.143-.2413 1.7619-.3505zM7.7369 8.3065a.0544.0544 0 0 1 .0548.0326c.0309.072.0225.1523-.0074.2209-.0116.028-.0474.0551-.0767.0616l-.2456.0546a.0227.0227 0 0 1-.0274-.0237l.023-.2886a.04.04 0 0 1 .0365-.0366l.2428-.0208zm2.7941-1.8543a.0366.0366 0 0 1 .0321.0549l-.5987 1.032a.2643.2643 0 0 1-.1552.126l-1.1227.3516a1.6503 1.6503 0 0 1-.3761.0712c-.249.0188-.9886.042-.9886.042l.0162-.0351a.0741.0741 0 0 1 .038-.0368l.35-.1487a.169.169 0 0 0 .0666-.0502l.5405-.6661c.0289-.0356.0666-.0697.1069-.0909.357-.1881.992-.4705 1.4368-.6192a.5085.5085 0 0 1 .1426-.0235l.5116-.0072zm-.6002-1.1984c1.2389-.109 2.9153-.1386 4.5168-.0173a.837.837 0 0 1 .2638.064c.5247.2209 1.4556.7042 2.4906 1.2969a.7764.7764 0 0 1 .1281.0917c.2742.2419.9689.9535.9689.9535l-.2167-.043a.2282.2282 0 0 1-.0844-.0351c-.4383-.2948-1.0782-.6785-1.6145-.949a.5915.5915 0 0 0-.2034-.0598 14.6895 14.6895 0 0 0-.8443-.0618c-.1138-.0047-.1913-.0237-.3026-.0803-.2127-.108-.728-.342-.9847-.44-.1098-.042-.1658-.0519-.2734-.0502-.441.0064-1.4457.0385-1.9588.0704a.2445.2445 0 0 1-.0521-.0025l-.2445-.0383c.6935-.1196 2.4077-.2725 3.1172-.3098l-.2887-.0966a.596.596 0 0 0-.1728-.0299c-.9698-.0218-2.3036-.0178-3.4321.067a.6098.6098 0 0 0-.2021.0504c-.3228.1419-1.11.5692-1.8994 1.0081-.2546.1416-.529.2952-.7731.4326 0 0 .0985-.1268.1175-.1515.0168-.0215.0219-.0255.0447-.0403.1018-.0684.4109-.2678.5343-.3585.2377-.1794.6128-.4956.8364-.6916a.6677.6677 0 0 0 .1288-.1529c.0723-.1171.1513-.2441.1999-.3145.0414-.0611.1123-.1038.2006-.1117zM4.655 2.404c.306-.0316.477.0875.477.3975v.1715c0 .3172-.171.4455-.477.4774a71.2552 71.2552 0 0 0-1.269.144v.4687c-.0886.0109-.1774.0218-.266.0331V2.5814a70.6625 70.6625 0 0 1 1.535-.1774zm14.2032-.0491a71.245 71.245 0 0 1 2.022.2263v.2444a68.7666 68.7666 0 0 0-.8741-.105v1.2707a94.0383 94.0383 0 0 0-.2663-.0299V2.6906a68.3322 68.3322 0 0 0-.8815-.0914v-.2443zM7.6494 2.1558v.2441a71.8527 71.8527 0 0 0-1.6641.1223v.3731a68.5725 68.5725 0 0 1 1.48-.1107v.2444a70.5409 70.5409 0 0 0-1.48.1104v.4094a69.7002 69.7002 0 0 1 1.6641-.1223v.2441a70.9377 70.9377 0 0 0-1.9245.145v-1.515a70.5346 70.5346 0 0 1 1.9245-.1448zm8.6326.4149c0-.3397.1683-.4097.5476-.384.3332.023.6658.0479.9988.0756.3295.0272.5469.1198.5469.4665v.6765c0 .3402-.1878.4015-.5469.3719a72.5525 72.5525 0 0 0-.9988-.0754c-.3628-.0245-.5476-.0946-.5476-.4546v-.6765zm-2.5812-.5284c.6426.0153 1.285.0395 1.9274.0726v.2441a70.7366 70.7366 0 0 0-1.6666-.0657v.3728c.4943.0139.9884.0327 1.4823.0567v.2444a70.4407 70.4407 0 0 0-1.4822-.0566v.4092a69.1564 69.1564 0 0 1 1.6666.066v.2441a71.29 71.29 0 0 0-1.9274-.0726v-1.515zm-3.344-.0013v1.0958c0 .3467-.1819.4228-.5484.4341a68.0289 68.0289 0 0 0-.9573.0361c-.3401.0153-.5479-.0494-.5479-.3926V2.1186l.2606-.0133v1.142c0 .0694.0595.126.1385.1223a70.1195 70.1195 0 0 1 1.2547-.0475c.0795-.0022.1323-.063.1323-.1324v-1.142c.089-.0025.1781-.0047.2675-.0067zm6.3245.3802c-.0792-.0054-.1387.0502-.1387.1295v.7491c0 .0694.0595.1423.1387.1478.4321.0287.8638.0613 1.2954.0978.0691.0059.1382-.0576.1382-.1268v-.7493c0-.0791-.0691-.1445-.1382-.1505a70.1864 70.1864 0 0 0-1.2954-.0976zm-5.1721-.3976c.479-.0035.958-.0017 1.4368.0047v.2441a72.1473 72.1473 0 0 0-1.536-.004c-.0693.0007-.1387.0608-.1387.1302v.759c0 .0694.0693.1381.1387.1374.4593-.004.9183-.0032 1.3776.002v-.4094a66.592 66.592 0 0 0-.7994-.0042v-.2443c.3534 0 .7068.0027 1.0602.0079v.8976a71.1228 71.1228 0 0 0-1.4896-.0064c-.3635.0025-.5484-.0603-.5484-.4136v-.6602c0-.3299.1651-.4383.4988-.4408zm-6.7546.6162l-.0206.0004a70.2289 70.2289 0 0 0-1.348.1522V3.35a71.0344 71.0344 0 0 1 1.348-.152c.0689-.0074.138-.0704.138-.1364v-.3068c0-.0694-.0691-.1218-.138-.1146l.0206-.0004z"/>',  # Peugeot
}


# bot16, 2026-10-06 (Robert: slouceni Ducato / Jumper / Boxer, "vcetne 3 log u sebe"): slouceny model (kategorie 233, tri sesterske vozy na jedne platforme) ma v dlazdici vic znackovych
# log vedle sebe. Klic = id slouceny kategorie, hodnota = id znackovych kategorii z BRAND_LOGOS v poradi zobrazeni (Fiat, Citroën, Peugeot).
# DRZET SYNCHRONNI s BRAND_LOGOS_MULTI v category.html (renderSubcats()).
BRAND_LOGOS_MULTI = {233: (269, 268, 288)}
_BRAND_SVG = '<svg role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">%s</svg>'


def _wi():
    """Modul web_i18n (IT/EN verze webu, docs/web_jazyky/README.md) - jen kdyz ho app.py nacetl a pozadavek NENI cesky. Za behu ho NIKDY neimportovat
    (jeho after_request se po prvnim pozadavku uz registrovat nesmi): bez 'import web_i18n' v app.py je tahle funkce vzdy None a vsechno zustava cesky."""
    m = sys.modules.get("web_i18n")
    return m if m is not None and m.jazyk() != "cs" else None


def _brand_thumb_html(cat_id, parent_id):
    """HTML znackove dlazdice podkategorie (jedno logo, u slouceneho modelu vic log), nebo None - bez loga se pouzije obrazek jako dosud."""
    multi = BRAND_LOGOS_MULTI.get(cat_id)
    if multi:
        return ('<div class="cs-media cs-media-brand cs-media-brand-multi"><span class="cs-brand-corner"></span>'
                + "".join(_BRAND_SVG % BRAND_LOGOS[b] for b in multi) + '</div>')
    svg = BRAND_LOGOS.get(cat_id) or BRAND_LOGOS.get(parent_id)
    if svg:
        return '<div class="cs-media cs-media-brand"><span class="cs-brand-corner"></span>' + _BRAND_SVG % svg + '</div>'
    return None


# QA nalez (2026-09-05, SEO_IMAGES_NOT_LAZY) - obrazky v admin-psanem
# CMS obsahu (intro_html/body_html/bottom_body_html) nemely loading="lazy"
# vubec. Mechanicky doplneno pri vlozeni do stranky (negative lookahead
# na uz existujici loading= atribut, ať se nic nepřepíše duplicitně) -
# NEMENI obsah v DB, jen SSR vystup.
_IMG_NO_LOADING_RE = re.compile(r"<img(?![^>]*\bloading=)([^>]*)>")


def _add_lazy_loading(html):
    if not html:
        return html
    return _IMG_NO_LOADING_RE.sub(lambda m: f'<img loading="lazy"{m.group(1)}>', html)


@app.get("/product.html")
def product_html_page():
    # product.html?id=N -> 301 na /produkt/<slug>, kdyz slug existuje
    # (bot15/bot3, 2026-09-02, QA seo.py SEO_CANONICAL_HAS_QUERY): stara
    # URL zustava funkcni (zalozky, admin "zobrazit v e-shopu", stare
    # odkazy v nabidkach), ale robot uz vidi jen jednu adresu misto dvou
    # se stejnym obsahem. Ostatni query parametry se prenaseji dal.
    pid = request.args.get("id")
    # Bezpecnostni nalez (bot3/revize kodu, 2026-09-02, zive overeno):
    # "?id=3938abc" spadlo na int(pid) hloub v _product_page_response
    # (MySQL WHERE id=%s tise preveden na 3938, radek se nasel, az
    # nasledny int() na retezec "3938abc" vyhodil ValueError -> 500).
    # Validace CELEHO retezce hned tady - jinak 404, nikdy nespadne dal.
    if pid is not None and not re.match(r"^\d+$", pid):
        return Response("Produkt nenalezen.", status=404, mimetype="text/plain; charset=utf-8")
    if pid and str(pid).isdigit():
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT slug FROM shop_products WHERE id=%s AND active=1 AND is_archived=0", (int(pid),))
                row = cur.fetchone()
        finally:
            conn.close()
        if row and row.get("slug"):
            rest = [(k, v) for k, v in request.args.items(multi=True) if k != "id"]
            target = f"/produkt/{row['slug']}"
            if rest:
                target += "?" + "&".join(f"{quote(k)}={quote(v)}" for k, v in rest)
            return redirect(target, code=301)
    return _product_page_response(pid)

def _product_rel_url(p):
    return f"/produkt/{p['slug']}" if p.get("slug") else f"/product.html?id={p['id']}"

@app.get("/produkt/<slug>")
def product_html_page_by_slug(slug):
    # Cista, klicovym-slovem popsana URL pro produkty (Robert 2026-08-09:
    # "mame spatne nazvy url pro SEO GEO") - stejny vzor jako
    # /kategorie/<slug> (SEO audit 2026-08-03). ?id= zustava funkcni
    # (interni odkazy, historicke zalozky), ale canonical a nove
    # generovane odkazy uz miri sem.
    # SOFT-404 OPRAVA (bot5, 2026-09-12, rozhodl bot3): tenhle dotaz drive
    # NEMEL filtr viditelnosti, takze skryty produkt (active=0 nebo
    # is_archived=1) routu prosel, `_product_page_response` nize uz filtr ma
    # (viz jeji SELECT), data nenasla a vratila prazdnou skorapku se stavem
    # **200**. Neexistujici slug pritom vracel spravne 404 - overeno
    # srovnanim pri archivaci karty 3942. Tykalo se to 111 ze 718 produktu
    # se slugem, ne jen te jedne.
    #
    # Filtr je tu zaroven PODMINKA, aby vubec fungovalo presmerovani nize:
    # vetev se `shop_product_redirects` se spousti jen kdyz slug nesedi na
    # zadny produkt. Dokud archivovany produkt slug "zabiral", zadny
    # redirect na nej nemohl vystrelit, i kdyby v tabulce byl.
    #
    # Staff vidi skryty produkt dal - nahled pred aktivaci je zamerna
    # funkce, ne mezera (stejne rozhodnuti jako products.py u
    # /api/shop/products/<id>, vcetne komentare "Staff (napr. nahled pred
    # aktivaci) dal vidi vse beze zmeny"). Bez tehle vyjimky by si admin
    # nemohl prohlednout stranku produktu, ktery jeste nezverejnil.
    #
    # `_is_staff_request()` sahá do DB (`current_user()`), proto se vola
    # PRED `get_conn()` - pooled spojeni sdili thread a volani uprostred
    # cizi transakce je znama past.
    is_staff = _is_staff_request()
    conn = get_conn()
    redirect_target = None
    row = None
    try:
        with conn.cursor() as cur:
            if is_staff:
                cur.execute("SELECT id FROM shop_products WHERE slug=%s", (slug,))
            else:
                cur.execute(
                    "SELECT id FROM shop_products WHERE slug=%s "
                    "AND active=1 AND is_archived=0",
                    (slug,),
                )
            row = cur.fetchone()
            if not row:
                cur.execute(
                    "SELECT p.slug AS new_slug FROM shop_product_redirects r "
                    "JOIN shop_products p ON p.id = r.product_id WHERE r.old_slug=%s",
                    (slug,),
                )
                rr = cur.fetchone()
                if rr:
                    redirect_target = rr["new_slug"]
    finally:
        conn.close()
    if not row:
        if redirect_target:
            return redirect(f"/produkt/{redirect_target}", code=301)
        return Response("Produkt nenalezen.", status=404, mimetype="text/plain")
    return _product_page_response(row["id"])

def _assembly_seo_sentence(cur, pid):
    """Popis navrhu sestavy (product_assemblies.shop_product_id = pid) z
    dat, ktera uz mame: karoserie (car_body_<id> v parts -> car_models +
    car_makes) a pocet dilu (parts bez karoserii) + nazvy pouzitych
    komponent (product_<id>). Bot15/bot3 2026-09-02, QA seo.py
    SEO_DUPLICATE_DESCRIPTION: sestavy ze sceny nemaji description ani
    short_description, meta popisek padal na sitovy default (= homepage).
    Vraci None, kdyz produkt neni sestava nebo data nejdou precist."""
    cur.execute(
        "SELECT data FROM product_assemblies WHERE shop_product_id=%s ORDER BY id DESC LIMIT 1",
        (pid,),
    )
    asm = cur.fetchone()
    if not asm:
        return None
    try:
        parts = (json.loads(asm["data"] or "{}") or {}).get("parts") or []
    except (TypeError, ValueError):
        return None
    body_ids, component_ids, n_parts = [], [], 0
    for p in parts:
        part_id = str((p or {}).get("part_id") or "")
        if part_id.startswith("car_body_"):
            try:
                body_ids.append(int(part_id[len("car_body_"):]))
            except ValueError:
                pass
            continue
        n_parts += 1
        if part_id.startswith("product_") and part_id[len("product_"):].isdigit():
            component_ids.append(int(part_id[len("product_"):]))
    car_label = None
    if body_ids:
        cur.execute(
            "SELECT mk.name AS make, m.name AS model FROM car_bodies b "
            "JOIN car_models m ON m.id=b.model_id LEFT JOIN car_makes mk ON mk.id=m.make_id "
            "WHERE b.id=%s",
            (body_ids[0],),
        )
        cr = cur.fetchone()
        if cr and cr.get("model"):
            # nazev modelu nese i rozmery ("... — 5309mm (L) ..."), do vety jen cast pred pomlckou
            model = cr["model"].split(" — ")[0].strip()
            # Robert 2026-09-06 (URGENTNI): "nesmime pouzivat puvodni oznaceni
            # karoserii... normalni nazev bude cely: Citroen Jumpy L2 rok" -
            # car_models.name nese i KRATKY INTERNI KOD v hranate zavorce
            # (puvodne vendor "[CI25]", ted vlastni "[K-045]", format se muze
            # jeste zmenit) - do VEREJNEHO textu nepatri zadny kod, jen
            # znacka+model+rok. Regex NEZAVISI na konkretnim formatu kodu
            # (libovolny obsah zavorky), aby pripadna zmena formatu kodu
            # nevyzadovala dalsi opravu tady.
            model = re.sub(r"\s*\[[^\]]*\]\s*", " ", model).strip()
            car_label = f"{cr['make']} {model}".strip() if cr.get("make") else model
    components = []
    if component_ids:
        # nejpouzivanejsi komponenty prvni, max 3 (meta description ~160 znaku)
        counts = {}
        for cid in component_ids:
            counts[cid] = counts.get(cid, 0) + 1
        top = sorted(counts, key=lambda cid: (-counts[cid], cid))[:3]
        cur.execute(
            "SELECT id, name FROM shop_products WHERE id IN (%s)" % ",".join(["%s"] * len(top)),
            tuple(top),
        )
        names = {r["id"]: r["name"] for r in cur.fetchall() if r.get("name")}
        components = [names[cid] for cid in top if cid in names]
    if not n_parts and not car_label:
        return None
    parts_label = "1 dílu" if n_parts == 1 else f"{n_parts} dílů"
    sentence = f"Návrh vestavby pro {car_label}" if car_label else "Návrh sestavy"
    if n_parts:
        sentence += f" z {parts_label}"
    if components:
        sentence += " (" + ", ".join(components) + ")"
    sentence += ". Z 3D konfigurátoru Logiman."
    return sentence

def _product_page_response(pid):
    # bot5, 2026-09-18 (Robert: karta 3960 "jen chyba" - staff-preview
    # slibena komentarem u product_html_page_by_slug/products.py se sem
    # nikdy nedostala): tahle funkce mela vlastni tvrde zakodovany
    # active=1 AND is_archived=0 filtr, takze i kdyz volajici routa
    # (product_html_page_by_slug) staff spravne pustila dal, tenhle
    # druhy dotaz staff stejne nenasel zadny radek -> window.__PRODUCT_ID__
    # se nikdy nenastavil -> klientsky JS hlasil "Produkt nenalezen" i
    # prihlasenemu adminovi. `_is_staff_request()` musi bezet PRED
    # get_conn() (pooled spojeni/current_user() past, viz
    # feedback_pooled_conn_rollback_trap).
    is_staff = _is_staff_request()
    conn = get_conn()
    extra_head = ""
    body_replacements = {}
    try:
        with conn.cursor() as cur:
            og = _get_og_site_defaults(cur)
            active_id = None
            expanded_ids = set()
            chain = []
            if pid:
                active_filter = "" if is_staff else " AND active=1 AND is_archived=0"
                cur.execute(
                    "SELECT id, name, slug, sku, description, short_description, price_czk_placeholder, stock_qty, availability_text, category_id, "
                    "unit, cfg_dily_id, is_board_material, is_profile_material, meta_title, meta_description, "
                    "sale_price_czk, sale_price_from, sale_price_until, dealer_discount_percent, "
                    "length_mm, width_mm, height_mm "
                    "FROM shop_products WHERE id=%s" + active_filter,
                    (pid,),
                )
                row = cur.fetchone()
                _w = _wi()
                if row and _w:
                    _w.prelozit_radky("kar", [row], ["name", "short_description", "description", "meta_title", "meta_description", "availability_text"])
                    row["price_czk_placeholder"] = None             # cena v EUR = faze 3 (bot5)
                if row:
                    # Kratky sufix " | Logiman" (bot15/bot3, 2026-09-02, QA
                    # seo.py SEO_TITLE_LONG: 52znakovy sufix "– Hliníkový
                    # stavebnicový systém pro užitková vozidla" tlacil title
                    # produktu na 70-80 znaku, Google orizne ~60 a nazev
                    # produktu se ztratil). Kategorie si dlouhy sufix nechavaji
                    # (kratke nazvy, jiny vzor - zadna kolize titulku). Admin
                    # meta_title ma prednost (stejne jako u kategorii; dosud se
                    # necetlo - SEO_GEO_AUDIT 1.2). Klientsky document.title v
                    # product.html drzet shodne. Sufix byl puvodne "Vandrawee"
                    # (bot9 2026-09-06: prepsano na "Logiman" - vandrawee.cz
                    # DNS zrusena a domena patri samostatnemu projektu).
                    og["title"] = row.get("meta_title") or f"{row['name']} | Logiman"
                    if row.get("slug"):
                        og["canonical"] = f"{PUBLIC_BASE_URL}/produkt/{row['slug']}"
                    if row.get("category_id"):
                        chain = _category_ancestor_chain(cur, row["category_id"])
                        active_id = row["category_id"]
                        expanded_ids = {c["id"] for c in chain[:-1]}
                    desc = (row.get("short_description") or "").strip()
                    # Robert 2026-08-08 ("oprav" tenky meta popisek u
                    # produktu bez short_description) - 465 z 565 aktivnich
                    # produktu (82 %) nema short_description vyplnene, takze
                    # se nejde spolehnout jen na rucni doplneni po jednom.
                    # Fallback na nazev kategorie (VSECHNY tyto produkty maji
                    # category_id, overeno) je univerzalne dostupny a lepsi
                    # nez holé "Cena: X Kč.".
                    if not desc and row.get("category_id"):
                        cur.execute("SELECT name FROM content_categories WHERE id=%s", (row["category_id"],))
                        cat_row = cur.fetchone()
                        if cat_row:
                            desc = f"{row['name']} – {cat_row['name']}."
                    # Navrhy sestav ze sceny / produkty bez kategorie (bot15,
                    # 2026-09-02): veta o karoserii + poctu dilu, jinak aspon
                    # nazev - at meta popisek nepada na sitovy default
                    # (SEO_DUPLICATE_DESCRIPTION s homepage). Rucni
                    # short_description ma vzdy prednost (viz vyse).
                    asm_sentence = None
                    if not (row.get("short_description") or "").strip():
                        asm_sentence = _assembly_seo_sentence(cur, pid)
                        if asm_sentence:
                            desc = (desc + " " if desc else "") + asm_sentence
                        elif not desc:
                            desc = f"{row['name']}."
                    if row.get("price_czk_placeholder") is not None:
                        # Robert 2026-08-08 ("uvadejme u ceny profilů, vedle ks
                        # také 3m") - stejne pripomenuti "ks" = "3 m" jako u
                        # karty v kategorii/detailu produktu.
                        unit_suffix = ""
                        if row.get("unit"):
                            unit_suffix = f" / {row['unit']}"
                            if row.get("is_profile_material") and row["unit"] == "ks" and not row.get("is_board_material"):
                                unit_suffix += " (3 m)"
                        desc = (desc + " " if desc else "") + f"Cena: {float(row['price_czk_placeholder']):.0f} Kč{unit_suffix}."
                    og["description"] = row.get("meta_description") or desc or og["description"]
                    # bot10, 2026-09-12 (stejna dira jako api/categories.py,
                    # nalez bot3): chybejici is_public filtr - tohle je
                    # OG obrazek pro socialni sdileni, verejny bez ohledu
                    # na prihlaseni.
                    cur.execute(
                        "SELECT filename FROM content_gallery_items WHERE owner_type='product' AND owner_id=%s "
                        "AND is_public=1 ORDER BY sort_order, id LIMIT 1",
                        (pid,),
                    )
                    gi = cur.fetchone()
                    if gi:
                        og["image"] = f"/content-files/gallery-items/{gi['filename']}"
                    else:
                        cur.execute(
                            "SELECT filename FROM shop_product_images WHERE product_id=%s ORDER BY sort_order, id LIMIT 1",
                            (pid,),
                        )
                        gi2 = cur.fetchone()
                        if gi2:
                            og["image"] = f"/content-files/gallery/{gi2['filename']}"

                    # Otočný náhled sestavy (bot16, api/turntable.py) - SEO
                    # rozšíření (bot3 pres toscanaccio-0b, 2026-09-02): SSR
                    # hero <img> primo v HTML (JS by ho jinak vykreslil az
                    # po fetch(), robot/rychly LCP to nestihne - widget pri
                    # mountu SSR obrazek prevezme bez opetovneho stahovani,
                    # viz komentar u initProductTurntable() v product.html),
                    # OG/JSON-LD obrazky z kanonicke sady, kdyz existuje.
                    # import az tady (ne na urovni modulu) - turntable.py se
                    # importuje az na konci app.py, viz komentar tam.
                    import turntable
                    tt_info = turntable.turntable_public_info(cur, pid)
                    tt_canonical = tt_info.get("canonical") or {}
                    if tt_canonical.get("hero_16x9"):
                        # OG image = hero 16:9 (bot3) - prepisuje vysi
                        # zjistenou galerijni fotku, kdyz kanonicka sada
                        # existuje (lepsi/konzistentnejsi nahled pro sdileni).
                        og["image"] = tt_canonical["hero_16x9"]
                    if tt_info.get("available") and tt_info.get("hero_url"):
                        hero_url = tt_info["hero_url"]
                        hero_w = tt_info.get("hero_width") or 2048
                        hero_h = tt_info.get("hero_height") or 1536
                        hero_alt = f"{row['name']} - pohled zepředu"
                        # srcset/sizes (bot3, LCP na mobilu) - bot16 doplnil
                        # 1024px varianty + hotovy hero_srcset retezec do
                        # canonical payloadu (2026-09-02). Muze byt None
                        # (produkt/sada bez 1024 varianty) - bez srcset
                        # atributu, prohlizec pouzije jen src (2048).
                        hero_srcset = tt_info.get("hero_srcset")
                        srcset_attr = f' srcset="{_og_escape(hero_srcset)}" sizes="(max-width: 640px) 100vw, 50vw"' if hero_srcset else ""
                        body_replacements['<div class="pd-turntable" id="pdTurntable"></div>'] = (
                            f'<div class="pd-turntable" id="pdTurntable">'
                            f'<img data-tt-hero src="{_og_escape(hero_url)}" width="{hero_w}" height="{hero_h}"{srcset_attr} '
                            f'alt="{_og_escape(hero_alt)}" decoding="async" fetchpriority="high"></div>'
                        )

                    image_url = og["image"]
                    if image_url and not image_url.startswith("http"):
                        image_url = PUBLIC_BASE_URL + image_url
                    # Product structured data (rich vysledky s cenou/dostupnosti
                    # ve vysledcich vyhledavani) - SEO audit 2026-08-03.
                    # image jako POLE [hero 4:3, hero 1:1, hero 16:9, bok,
                    # zezadu, shora] (bot3), kdyz kanonicka sada existuje -
                    # jinak beze zmeny (jeden retezec jako u ostatnich
                    # produktu bez otocneho nahledu).
                    product_ld_image = image_url
                    if tt_canonical:
                        abs_images = []
                        for key in ("hero", "hero_1x1", "hero_16x9", "side", "back", "top"):
                            u = tt_canonical.get(key)
                            if u:
                                abs_images.append(u if u.startswith("http") else PUBLIC_BASE_URL + u)
                        if abs_images:
                            product_ld_image = abs_images
                    product_ld = {
                        "@context": "https://schema.org",
                        "@type": "Product",
                        "name": row["name"],
                        "sku": row.get("sku"),
                        "description": og["description"],
                        "image": product_ld_image,
                        "url": og.get("canonical") or request.url,
                    }
                    # QA nalez (2026-09-05, SEO_REC_PRODUCT_NO_DIMENSIONS) -
                    # fyzicke rozmery v DB (shop_products.length_mm/width_mm/
                    # height_mm) uz existuji a jsou vyplnene, ale do JSON-LD
                    # se nikdy nedostaly. schema.org nema vlastni "length",
                    # depth je bezna konvence. U profilovych produktu length_mm
                    # je standardni/vychozi delka tyce (ne konecna nakoupena
                    # delka po prirezu) - stejne jako u ostatnich pevnych dilu
                    # jde o smysluplny fyzicky rozmer produktu.
                    for schema_key, db_key in (("depth", "length_mm"), ("width", "width_mm"), ("height", "height_mm")):
                        val = row.get(db_key)
                        if val:
                            product_ld[schema_key] = {"@type": "QuantitativeValue", "value": float(val), "unitCode": "MMT"}
                    if row.get("price_czk_placeholder") is not None:
                        # Zivy nalez (bot3/revize kodu, 2026-09-02): JSON-LD
                        # posilal holy price_czk_placeholder - jakmile by byla
                        # aktivni akcni cena/kupon, Google by ukazoval jinou
                        # cenu nez kosik. Anonymni vetev _effective_unit_price
                        # (Google = neprihlaseny navstevnik, zadny kupon v
                        # URL) - stejna funkce jako stranka produktu/kosik/
                        # nahled rezu. Lokalni import (products.py importuje
                        # z app.py, ne naopak - viz jeho hlavicka).
                        from products import _effective_unit_price
                        ld_price, _ld_basis = _effective_unit_price(cur, row, user=None, coupon_code=None)
                        product_ld["offers"] = {
                            "@type": "Offer",
                            "priceCurrency": "CZK",
                            "price": f'{ld_price:.2f}',
                            # Robert ("na detailech produktů chybí dostupnost") - 99,8 % katalogu
                            # ma stock_qty=0 (rezane/objednavane na miru, ne skladem po kusech),
                            # cisty stock_qty>0 test tak skoro cely katalog oznacoval jako
                            # OutOfStock (Google pak takove nabidky degraduje/neukazuje cenu).
                            # availability_text (napr. "3 - 5 týdnů") znamena realne objednatelne.
                            "availability": ("https://schema.org/InStock"
                                             if (row.get("stock_qty") or 0) > 0 or row.get("availability_text")
                                             else "https://schema.org/OutOfStock"),
                            "url": og.get("canonical") or request.url,
                        }
                    # BreadcrumbList JSON-LD (bot15, 2026-09-02, QA seo.py
                    # nalez SEO_NO_BREADCRUMB_JSONLD - kategorie ho maji,
                    # produkty dosud ne): kategorie z retezce + produkt jako
                    # posledni polozka (stejny vzor jako _category_page_response).
                    product_url = og.get("canonical") or request.url
                    breadcrumb_items = [
                        {"@type": "ListItem", "position": i + 1, "name": c["name"],
                         "item": PUBLIC_BASE_URL + _category_rel_url(c)}
                        for i, c in enumerate(chain)
                    ]
                    breadcrumb_items.append({
                        "@type": "ListItem", "position": len(chain) + 1,
                        "name": row["name"], "item": product_url,
                    })
                    breadcrumb_ld = {
                        "@context": "https://schema.org",
                        "@type": "BreadcrumbList",
                        "itemListElement": breadcrumb_items,
                    }
                    extra_head = (
                        _ld_json_script(breadcrumb_ld)
                        + _ld_json_script(product_ld)
                        + f'<script>window.__PRODUCT_ID__={int(pid)};</script>\n'
                    )

                    # --- SSR telesneho obsahu (bot15, 2026-09-02, QA seo.py
                    # nalez SEO_H1_PLACEHOLDER: 41/41 produktu ve vzorku melo
                    # v HTML <h1>Načítám…</h1>, prazdne drobecky a prazdny
                    # popis - JS je doplni az po fetch(/api/products/<id>),
                    # robot bez JS / v prvni vlne indexace vidi jen
                    # placeholder). Stejny vzor jako v _category_page_response
                    # vyse: vkladame TENTYZ HTML, jaky vygeneruje klientsky
                    # JS (renderBreadcrumb()/loadProduct() v product.html),
                    # ktery ho po nacteni beze zmeny chovani prepise.
                    body_replacements['<h1 class="pd-title" id="pdTitle">Načítám…</h1>'] = (
                        f'<h1 class="pd-title" id="pdTitle">{_og_escape(row["name"])}</h1>'
                    )
                    crumb_html = '<a href="/">Kategorie</a>'
                    for c in chain:
                        crumb_html += (f'<span class="sep">›</span>'
                                       f'<a href="{_category_rel_url(c)}">{_og_escape(c["name"])}</a>')
                    crumb_html += f'<span class="sep">›</span>{_og_escape(row["name"])}'
                    body_replacements['<div class="breadcrumb" id="breadcrumb"></div>'] = (
                        f'<div class="breadcrumb" id="breadcrumb">{crumb_html}</div>'
                    )
                    # Popis: klient dela escapeHtml(p.description ||
                    # p.short_description) do innerHTML (bezpecnost, audit
                    # bot11 1.8) - tady totez, cisty text bez HTML.
                    desc_text = (row.get("description") or row.get("short_description") or asm_sentence or "").strip()
                    if desc_text:
                        body_replacements['<div class="pd-desc" id="pdDesc"></div>'] = (
                            f'<div class="pd-desc" id="pdDesc">{_og_escape(desc_text)}</div>'
                        )
            # Robert 2026-08-11 ("problikne levé menu... probliká
            # podtržítko") - #catTree tu byl (na rozdil od index.html/
            # category.html) CISTE klientsky-JS (loadProduct() ho renderuje
            # az po fetch("/api/categories")), takze sidebar pri kazdem
            # otevreni produktu nejdriv problikl prazdny/nizky a pak
            # vyskocil na plnou vysku - stejny bug jako u /blok, /panel.
            _add_category_tree_ssr(cur, body_replacements, active_id, expanded_ids)
    finally:
        conn.close()
    return _render_og_page("product.html", og, extra_head, body_replacements)

def _category_rel_url(c):
    # Korenovy tvar URL (Robert 2026-09-24 pres bot3: "v URL přece
    # nechceme slovo kategorie!!!") - drive f"/kategorie/{slug}", viz
    # git historie. /category.html?id= zustava funkcni fallback pro
    # kategorie bez slugu.
    return f"/{c['slug']}" if c.get("slug") else f"/category.html?id={c['id']}"

def _category_page_response(cat_id):
    # SKRYTA KATEGORIE (bot5, 2026-09-12, rozhodl bot3): tahle funkce
    # NEMELA filtr viditelnosti vubec, takze kategorie s `is_visible=0` se
    # anonymovi vykreslila CELA (nazev, meta, strom, produkty) - na rozdil
    # od produktu, kde stejny nalez koncil jen prazdnou skorapkou. Nebyl to
    # tedy jen spatny stavovy kod, ale skutecny unik neverejneneho obsahu.
    #
    # Filtr patri SEM, ne jen do routy se slugem, protoze funkce ma DVA
    # vstupni body: `/kategorie/<slug>` i `/category.html?id=<id>`. Oprava
    # jen v jednom z nich by druhy nechala otevreny.
    #
    # Staff vidi skryte dal - prohlednout si nezverejnenou kategorii pred
    # publikaci je zamerna funkce (stejne rozhodnuti jako u produktu).
    # Pouziva se `_category_tree_show_hidden()`, tedy tyz predikat, jakym
    # se uz rozhoduje o skrytych vetvich stromu kategorii - ne vlastni
    # druha definice "kdo je staff", ktera by se casem rozesla.
    #
    # Vola se PRED `get_conn()`: sahá do DB pres `current_user()` a pooled
    # spojeni sdili thread, takze volani uprostred cizi transakce je past.
    zobraz_skryte = _category_tree_show_hidden()
    conn = get_conn()
    extra_head = ""
    body_replacements = {}
    nenalezeno = False
    try:
        with conn.cursor() as cur:
            og = _get_og_site_defaults(cur)
            active_id = None
            expanded_ids = set()
            if cat_id:
                cur.execute(
                    "SELECT id, name, slug, meta_title, meta_description, image_filename, og_image_filename, is_visible "
                    "FROM content_categories WHERE id=%s",
                    (cat_id,),
                )
                row = cur.fetchone()
                # Neexistujici i skryta kategorie konci stejne: 404 nize.
                # Drive se v obou pripadech vyrenderovala stranka se stavem
                # 200 - u neexistujici prazdna (soft-404), u skryte plna.
                if not row or (not row["is_visible"] and not zobraz_skryte):
                    nenalezeno = True
                    row = None
                _w = _wi()
                if row and _w:
                    _w.prelozit_radky("kat", [row], ["name", "meta_title", "meta_description"])
                if row:
                    og["title"] = row.get("meta_title") or f"{row['name']} – {_w.nazev_webu() if _w else 'Hliníkový konstrukční stavebnicový systém s drážkami'}"
                    # Fallback popis, pokud kategorie v adminu nema vlastni
                    # meta_description vyplneny - at nikdy nejde ven prazdny
                    # <meta name="description"> (viz SEO audit 2026-08-03).
                    og["description"] = row.get("meta_description") or (
                        f"{row['name']} – hliníkové profilové konstrukce a systémy na míru. "
                        "Navrhněte si řešení v 3D konfigurátoru, odborné poradenství a rychlé dodání."
                    )
                    img_name = row.get("og_image_filename") or row.get("image_filename")
                    if img_name:
                        og["image"] = f"/content-files/categories/{img_name}"
                    else:
                        # bot7 2026-09-27 (Robert pres bot3: "kazda kategorie
                        # ma prevzit obrazek od nejakeho zastupce uvnitr") -
                        # bez vlastniho og_image_filename/image_filename
                        # pouzij stejny fallback jako .cat-subcats dlazdice.
                        fallback_img = _category_representative_image_url(cur, row["id"])
                        if fallback_img:
                            og["image"] = fallback_img
                    if row.get("slug"):
                        og["canonical"] = PUBLIC_BASE_URL + _category_rel_url(row)

                    chain = _category_ancestor_chain(cur, row["id"])
                    if _w:
                        _w.prelozit_radky("kat", chain, ["name"])
                    active_id = row["id"]
                    expanded_ids = {c["id"] for c in chain[:-1]}

                    def _cat_abs_url(c):
                        return PUBLIC_BASE_URL + _category_rel_url(c)

                    breadcrumb_ld = {
                        "@context": "https://schema.org",
                        "@type": "BreadcrumbList",
                        "itemListElement": [
                            {"@type": "ListItem", "position": i + 1, "name": c["name"], "item": _cat_abs_url(c)}
                            for i, c in enumerate(chain)
                        ],
                    }

                    # Robert 2026-08-09 ("kdyz vstoupim do podkategorie,
                    # nejdriv se zobrazi polozky v defaultnim poradi, a za
                    # necelou sekundu se seradi podle ceny - problik") -
                    # SSR (tahle funkce, plni pocatecni HTML pri primem
                    # nacteni stranky) volala bez sort= => default "name"
                    # (viz _category_products_with_images nize), zatimco
                    # client-side loadCategory() v category.html hned po
                    # nacteni znovu fetchuje /api/categories/<id>/content
                    # BEZ sort= parametru, ktery se serverove defaultuje na
                    # "price_asc" (viz category_content_get) - druhy
                    # (spravny) render tak viditelne prepsal prvni (SSR,
                    # jmenem serazeny) obsah. Sjednoceno na price_asc, aby
                    # SSR uz rovnou vratil finalni poradi bez prekresleni.
                    # bot3 2026-09-25 (rozhodnuti PO zmereni dopadu - prvni
                    # pokus byl strop 800/693 KiB HTML u kategorie 149, bot3
                    # to vratil zpet jako zbytecne velke pro mobil/data):
                    # SSR strop 100, NE vic, ze tri duvodu:
                    # 1) 693 KiB na JEDNU kategorii (600 polozek) je zbytecne
                    #    velke - plati to uzivatel na mobilu/datech, ne jen
                    #    Google.
                    # 2) VSECHNY produkty maji vlastni URL v sitemap.xml
                    #    (663 z 797 zaznamu, overeno 2026-09-25) - robot se
                    #    k nim dostane primo, nepotrebuje je vyjmenovane i
                    #    v kategorii.
                    # 3) Po zavedeni dedeneho vypisu (viz vyse) je zbytek
                    #    dostupny pres podkategorie - citelnejsi pro
                    #    uzivatele i robota nez jedna nekonecna stranka.
                    # Skutecne strankovani zatim NESTAVET (bot3: "prace
                    # navic bez uzitku") - az bude kategorie s tisici
                    # polozek, nebo Robert vyslovne rekne, ze chce v
                    # kategorii listovat vsechno.
                    products = _category_products_with_images(cur, row["id"], limit=100, sort="price_asc")
                    if _w:
                        _w.prelozit_radky("kar", products, ["name", "availability_text"])
                        for _p in products:
                            _p["price_czk_placeholder"] = None          # cena v EUR = faze 3 (bot5); v Kc se na jazykovem webu neukazuje
                    collection_ld = {
                        "@context": "https://schema.org",
                        "@type": "CollectionPage",
                        "name": og["title"],
                        "description": og["description"],
                        "hasPart": [
                            {"@type": "Product", "name": p["name"],
                             "url": PUBLIC_BASE_URL + _product_rel_url(p)}
                            for p in products
                        ],
                    }
                    extra_head = (
                        _ld_json_script(breadcrumb_ld) + _ld_json_script(collection_ld)
                        + f'<script>window.__CATEGORY_ID__={int(row["id"])};</script>\n'
                    )

                    # --- SSR (server-side render) telesneho obsahu ---------
                    # Robot (i nastroj, ktery nevykonava JS, nebo ho vykona az
                    # se zpozdenim - Google "druha vlna") jinak vidi jen
                    # placeholder "Nacitam..." v H1 a prazdne divy, JS je
                    # dopoln az po fetch()i. SSR sem vklada STEJNY HTML, jaky
                    # by vygeneroval klientsky JS (renderBreadcrumb/
                    # renderSubcats/renderProducts nize v category.html) -
                    # po nacteni JS ho beze zmeny chovani prepise (identicky
                    # nebo aktualizovany obsah), viz SEO audit 2026-08-03.
                    body_replacements['<h1 class="cat-title" id="catTitle">Načítám…</h1>'] = (
                        f'<h1 class="cat-title" id="catTitle">{_og_escape(row["name"])}</h1>'
                    )

                    crumb_html = '<a href="/">Kategorie</a>'
                    for i, c in enumerate(chain):
                        crumb_html += '<span class="sep">›</span>'
                        crumb_html += (_og_escape(c["name"]) if i == len(chain) - 1
                                       else f'<a href="{_category_rel_url(c)}">{_og_escape(c["name"])}</a>')
                    body_replacements['<div class="breadcrumb" id="breadcrumb"></div>'] = (
                        f'<div class="breadcrumb" id="breadcrumb">{crumb_html}</div>'
                    )

                    cur.execute(
                        "SELECT id, name, slug, image_filename FROM content_categories "
                        "WHERE parent_id=%s AND is_visible=1 ORDER BY sort_order, name",
                        (row["id"],),
                    )
                    subcats = cur.fetchall()
                    if subcats and _w:
                        _w.prelozit_radky("kat", subcats, ["name"])
                    if subcats:
                        items_html = ""
                        # QA nalez (2026-09-05, SEO_HERO_IMG_NO_DIMENSIONS/
                        # SEO_HERO_IMG_LAZY): prvni obrazek stranky (LCP) nesmi
                        # byt lazy a mel by mit width/height (CLS) - na rozdil
                        # od produktove hero fotky to tu chybelo. Ostatni
                        # nahledy zustavaji lazy beze zmeny.
                        for idx, c in enumerate(subcats):
                            # Robert 2026-08-09 ("nahledy kategorií musí
                            # převzít zcela styl jaký mají náhledy produktů") -
                            # cs-thumb obalen do cs-media (stejny vzor jako
                            # .cp-media u produktu), viz webapp/category.html
                            # renderSubcats() - drzet obe verze synchronni.
                            # Robert: "ty znacky aut pridejme i do teto
                            # urovně" - model-level podkategorie (napr.
                            # "Vestavby pro Citroën Jumpy" pod znackou
                            # Citroën) sami v BRAND_LOGOS nejsou, ale jejich
                            # RODIC (row["id"]) ano - zdedi stejne logo.
                            brand_thumb = _brand_thumb_html(c["id"], row["id"])
                            if brand_thumb:
                                thumb = brand_thumb
                            else:
                                # bot7 2026-09-27 (Robert pres bot3: "kazda
                                # kategorie ma prevzit obrazek od nejakeho
                                # zastupce uvnitr") - vlastni obrazek, jinak
                                # "vypujceny" od prvni podkategorie/produktu
                                # bez vlastniho - viz _category_representative_
                                # image_url() v api/app.py, drzet synchronni s
                                # renderSubcats() ve webapp/category.html.
                                thumb_url = (
                                    f'/content-files/categories/{quote(c["image_filename"])}' if c.get("image_filename")
                                    else _category_representative_image_url(cur, c["id"])
                                )
                                if thumb_url:
                                    if idx == 0:
                                        dims = _content_file_dimensions(thumb_url)
                                        dim_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
                                        thumb = (f'<div class="cs-media"><img class="cs-thumb" src="{thumb_url}" '
                                                 f'alt="{_og_escape(c["name"])}"{dim_attrs} fetchpriority="high"></div>')
                                    else:
                                        thumb = (f'<div class="cs-media"><img class="cs-thumb" src="{thumb_url}" '
                                                 f'alt="{_og_escape(c["name"])}" loading="lazy"></div>')
                                else:
                                    thumb = ""
                            items_html += (f'<li><a href="{_category_rel_url(c)}">{thumb}'
                                           f'<span class="cs-name">{_og_escape(c["name"])}</span></a></li>')
                        body_replacements['<div class="cat-subcats" id="subcatsWrap" style="display:none;">'] = (
                            '<div class="cat-subcats" id="subcatsWrap">'
                        )
                        body_replacements['<ul id="subcatsList"></ul>'] = f'<ul id="subcatsList">{items_html}</ul>'

                    cur.execute("SELECT intro_html, body_html, bottom_body_html FROM content_pages WHERE category_id=%s", (row["id"],))
                    page_row = cur.fetchone()
                    if page_row and _w:
                        _w.prelozit_dict("str:%d" % row["id"], page_row, ["intro_html", "body_html", "bottom_body_html"])
                    # Robert 2026-08-09 ("rozdel text dulezity nad mrizku
                    # podkategorií a zbylý do spodni casti") - kratky uvod
                    # (intro_html) hned pod nadpisem PRED mrizkou podkategorii
                    # (SEO/GEO - prvni odstavec bereno AI enginy jako shrnuti),
                    # zbytek (body_html) presunut NIZ, za vypis produktu (viz
                    # umisteni #catIntro/#catBody v webapp/category.html).
                    intro_html = _add_lazy_loading((page_row or {}).get("intro_html") or "")
                    if intro_html:
                        body_replacements['<div class="cat-body cat-intro" id="catIntro" style="display:none;"></div>'] = (
                            f'<div class="cat-body cat-intro" id="catIntro">{intro_html}</div>'
                        )
                    body_html = _add_lazy_loading((page_row or {}).get("body_html")) or '<p class="cat-empty-body">Zatím bez obsahu.</p>'
                    body_html = _strip_empty_faq_block(body_html)
                    body_replacements['<div class="cat-body" id="catBody"></div>'] = f'<div class="cat-body" id="catBody">{body_html}</div>'
                    # Robert 2026-08-08 ("SEO a GEO obsah kategorií") - spodni
                    # popis (FAQ + interni prolinkovani) byl doteď JEN
                    # klientsky vykreslovany (#catBottomBody, viz
                    # category.html renderCategory()), tedy neviditelny pro
                    # SSR/roboty bez JS - presne ten typ strukturovaneho FAQ
                    # obsahu, ktery GEO (AI vyhledavace/odpovedni enginy) i
                    # klasicti crawleri nejvic ocenuji. Doplneno symetricky
                    # ke catBody vyse.
                    bottom_body_html = _add_lazy_loading((page_row or {}).get("bottom_body_html") or "")
                    bottom_body_html = _strip_empty_faq_block(bottom_body_html)
                    if bottom_body_html:
                        body_replacements['<div class="cat-body cat-body-bottom" id="catBottomBody"></div>'] = (
                            f'<div class="cat-body cat-body-bottom" id="catBottomBody">{bottom_body_html}</div>'
                        )

                    # FAQPage JSON-LD (bot10, 2026-08-28, schvaleno bot3) -
                    # zabaleni JIZ EXISTUJICIHO seo-faq bloku (viz
                    # _extract_faq_pairs vys), typicky v bottom_body_html,
                    # vyjimecne v body_html (1 kategorie) - zkontrolovat oba.
                    faq_pairs = _extract_faq_pairs(bottom_body_html) or _extract_faq_pairs(body_html)
                    if faq_pairs:
                        extra_head += _ld_json_script(_faq_page_ld(faq_pairs))

                    if products:
                        cards_html = ""
                        # QA nalez (2026-09-05): pokud stranka NEMA podkategorie
                        # (jejich prvni nahled uz dostal hero traktovani vyse),
                        # je prvni produktovy obrazek skutecnym LCP prvkem.
                        page_hero_used = bool(subcats)
                        # bot3 2026-09-25: strop 100, sjednoceny s fetch
                        # limitem vyse (products uz stejne nikdy neni delsi) -
                        # duvod viz komentar u volani _category_products_
                        # with_images o par desitek radku vys (693 KiB HTML
                        # pri 600 polozkach, produkty maji vlastni URL v
                        # sitemap.xml, zbytek dostupny pres podkategorie).
                        for idx, p in enumerate(products[:100]):
                            # Robert 2026-08-09 ("škaredý rozhoz na pul sekundy při
                            # načítání seznamu produktů") - SSR karta MUSI byt 1:1
                            # se strukturou, kterou generuje webapp/category.html
                            # ::renderProducts(), jinak po dobehnuti klientskeho
                            # fetch/re-renderu obrazek/cena viditelne "skoci"
                            # (chybejici .cp-media obal, ignorovany hover-mode,
                            # jine formatovani ceny). Drz tento blok synchronni
                            # s renderProducts() při každé změně jednoho z nich.
                            is_profile_unit = (bool(p.get("is_profile_material")) and p.get("unit") == "ks"
                                                and not p.get("is_board_material"))
                            price = ""
                            if p.get("price_czk_placeholder") is not None:
                                price_fmt = f'{p["price_czk_placeholder"]:,.0f}'.replace(",", " ")
                                price = (f'{price_fmt} Kč / {_og_escape(p["unit"] or "")}'
                                         + (" (3 m)" if is_profile_unit else "")
                                         + ' <span class="cp-price-vat">bez DPH</span>')
                            hover_mode = p.get("price_visible_default") is False
                            avail_text = p.get("availability_text") or (
                                "Skladem" if (p.get("stock_qty") or 0) > 0
                                else ("3 - 5 týdnů" if p.get("stock_qty") == 0 else "")
                            )
                            # Robert 2026-08-09 ("po najetí na prehledové okno produktu,
                            # hover, nech zmizí název a cena se ukáže namísto názvu") -
                            # cena u hover-mode karet uz neni panel pres obrazek, ale
                            # prekryva primo .cp-name (.cp-name-row, viz CSS). Panel
                            # pres obrazek zustava jen pro dostupnost.
                            price_block, hover_panel, name_swap_price = "", "", ""
                            if hover_mode:
                                if price and p.get("hover_show_price") is not False:
                                    name_swap_price = f'<div class="cp-name-price">{price}</div>'
                                if avail_text and p.get("hover_show_availability"):
                                    hover_panel = f'<div class="cp-hover-panel"><div class="cp-avail">{_og_escape(avail_text)}</div></div>'
                            elif price:
                                price_block = f'<div class="cp-price">{price}</div>'
                            if p.get("image_url"):
                                is_hero = (not page_hero_used) and idx == 0
                                # Robert pres bot3, 2026-09-25, 2. kolo - dim_attrs
                                # ted VZDY (drive jen u hero obrazku) - .cp-media uz
                                # nema vlastni aspect-ratio (viz category.html CSS),
                                # bez width/height atributu na KAZDEM obrazku by se
                                # dlazdice pri nacitani poskakovaly (CLS). Cena
                                # navic je zanedbatelna - _content_file_dimensions
                                # je @lru_cache(512), viz api/app.py.
                                dims = _content_file_dimensions(p["image_url"])
                                dim_attrs = f' width="{dims[0]}" height="{dims[1]}"' if dims else ""
                                if is_hero:
                                    page_hero_used = True
                                    img_inner = f'<img class="cp-image" src="{p["image_url"]}"{dim_attrs} fetchpriority="high" alt="{_og_escape(p["name"])}">'
                                else:
                                    img_inner = f'<img class="cp-image" src="{p["image_url"]}"{dim_attrs} loading="lazy" alt="{_og_escape(p["name"])}">'
                                if p.get("image_url_hover"):
                                    img_inner += f'<img class="cp-image-hover" src="{p["image_url_hover"]}" loading="lazy" alt="">'
                            else:
                                img_inner = ""
                            # bot5 2026-08-10 (Robert: "ty ikony Slotu se
                            # nacitaji opozdene jakoby dodatecne po nacteni
                            # stranky") - presne ten "problik" bug popsany v
                            # komentari vyse, jen u noveho prvku (odznak),
                            # ktery jsem pri zavadeni omylem pridal jen do
                            # klientskeho renderProducts(), ne sem. Trida
                            # MUSI odpovidat grooveBadgeClass() v category.html.
                            groove_badge = _groove_badges_html(p.get("groove_family"), p.get("cross_section_label"), _og_escape)
                            # Robert 2026-08-11 - odznak zavitu vedle
                            # odznaku Slotu, viz _thread_badge_html.
                            thread_badge = _thread_badge_html(p["name"], _og_escape)
                            # Robert pres bot3, 2026-09-25 - odznaky umisteni/
                            # profilu PRES render (protilehle rohy .cp-media),
                            # viz _umisteni_badge_html/_profil_badge_html vyse.
                            umisteni_badge = _umisteni_badge_html(p.get("umisteni_kod"), p.get("umisteni_nazev"), _og_escape)
                            profil_badge = _profil_badge_html(p.get("profil_mm"), _og_escape)
                            cards_html += (
                                f'<div class="cat-product-card{" cp-hover-mode" if hover_mode else ""}">'
                                f'<a href="{_og_escape(_product_rel_url(p))}" style="text-decoration:none;color:inherit;">'
                                f'<div class="cp-media">{img_inner}{umisteni_badge}{profil_badge}{hover_panel}</div>'
                                f'<div class="cp-name-row"><div class="cp-name" title="{_og_escape(p["name"])}">{_og_escape(p["name"])}</div>{name_swap_price}</div>'
                                f'{groove_badge}{thread_badge}'
                                f'{price_block}'
                                '</a></div>'
                            )
                        body_replacements['<div class="cat-products" id="productsWrap" style="display:none;">'] = (
                            '<div class="cat-products" id="productsWrap">'
                        )
                        body_replacements['<div class="cat-product-grid" id="productGrid"></div>'] = (
                            f'<div class="cat-product-grid" id="productGrid">{cards_html}</div>'
                        )

            _add_category_tree_ssr(cur, body_replacements, active_id, expanded_ids)
    finally:
        conn.close()
    if nenalezeno:
        return Response("Kategorie nenalezena.", status=404, mimetype="text/plain")
    return _render_og_page("category.html", og, extra_head, body_replacements)

def _index_page_response():
    # Robert 2026-08-09 ("pri otevirani webu to poskakuje") - #catTree na
    # index.html byl dosud ciste JS-only (prazdny v syrovem HTML, viz
    # webapp/index.html) - box levy sidebar tak pri kazdem otevreni domovske
    # stranky nejdriv naskocil jen s titulkem a az po dobehnuti fetch()e
    # "/api/categories" se viditelne roztahl na plnou vysku stromu. Stejny
    # fix jako u _category_page_response nize (bot6/bot4, kategorie/
    # produkty) - SSR rovnou vlozi hotovy strom, klientsky JS ho pak jen
    # (beze zmeny chovani) pretka identickym obsahem.
    conn = get_conn()
    body_replacements = {}
    extra_head = ""
    try:
        with conn.cursor() as cur:
            og = _get_og_site_defaults(cur)
            _add_category_tree_ssr(cur, body_replacements)

            # Homepage carousel (Robert pres bot3, 2026-09-27: "stejny
            # carousel jako je na homepage logimanu") - 100% SSR, stejny
            # duvod jako mozaika/hlasky nize.
            cur.execute("SELECT * FROM homepage_carousel_slides WHERE is_visible=1 ORDER BY sort_order ASC, id ASC")
            carousel_slides = cur.fetchall()
            _w = _wi()
            if _w:
                _w.prelozit_radky("dom", carousel_slides, ["caption_text"], predpona_pk="slide")
            body_replacements['<div class="hp-carousel" id="hpCarousel"></div>'] = (
                f'<div class="hp-carousel" id="hpCarousel">{_render_homepage_carousel_html(carousel_slides)}</div>'
            )

            # Homepage mozaika (Robert: "system sudeho poctu oken...
            # pozitivni vliv na SEO/GEO") - SSR rovnou (zadny klientsky
            # JS render, na rozdil od stromu kategorii vyse - jednodussi
            # a nehrozi zadny SSR/JS nesoulad, viz drivejsi "poskakovani"
            # bug u produktoveho gridu). ItemList JSON-LD navic pro
            # GEO/AI vyhledavace (strukturovana data o obsahu homepage).
            cur.execute("SELECT * FROM homepage_blocks WHERE is_visible=1 ORDER BY sort_order ASC, id ASC")
            blocks = cur.fetchall()
            if _w:
                blocks = [b for b in blocks if b["id"] not in _w.SKRYTE_BLOKY]
                _w.prelozit_radky("dom", blocks, ["title", "meta_description", "body_html"], predpona_pk="blok")
            # gallery_category (Robert: "tato nová bude pouze pro stoly,
            # a z predeslé pro vestvaby ty fotky stolů přesuneš") - kazda
            # gallery_preview dlazdice muze chtit jinou kategorii fotek,
            # takze dotaz zvlast pro kazdou DISTINCT hodnotu skutecne
            # pouzitou mezi viditelnymi dlazdicemi (typicky 1-2, ne
            # jeden spolecny dotaz pro vsechny).
            # bot16, 2026-09-13: prepojeno na content_photo_library (stejny
            # zdroj jako /realizace.html - api/gallery.py). Puvodne cetlo
            # primo shop_gallery_images, ale ta uz od fe93b24e (2026-09-12,
            # bot10) nedostava zadne nove zapisy - admin edituje jen
            # content_photo_library, takze mozaika na homepage byla
            # zamrzla na stavu z migrace a tise by se rozjizdela od
            # kazdeho dalsiho zasahu v adminu. Stejny filtr/razeni jako
            # gallery_public_list() v api/gallery.py.
            gallery_images_by_category = {}
            needed_categories = {b.get("gallery_category") for b in blocks if b.get("gallery_preview")}
            for cat in needed_categories:
                sql = "SELECT realizace_tag AS category, file_path, title FROM content_photo_library WHERE is_public=1 AND realizace_tag IS NOT NULL"
                params = []
                if cat:
                    sql += " AND realizace_tag=%s"
                    params.append(cat)
                sql += " ORDER BY sort_order ASC, id ASC LIMIT 10"
                cur.execute(sql, params)
                gallery_images_by_category[cat] = [
                    {"url": f"/{g['file_path']}", "title": g["title"]}
                    for g in cur.fetchall()
                ]
            # Robert pres bot3, 2026-09-27 ("jednu dlazdici mozaiky dej
            # napravo od carouselu") - prazdne misto napravo od carouselu
            # na sirokych monitorech (pevna 920x368, viz komentar u
            # .hp-carousel-viewport v index.html) vyplni 1. dlazdice
            # mozaiky misto prazdna. #hpTopTile je staticky placeholder
            # uvnitr .hp-top-row (obali #hpCarousel+#hpTopTile) primo v
            # index.html - #hpMosaic pod tim dostane jen ZBYVAJICI
            # dlazdice (bez te prvni, aby se needlela).
            first_tile_html, rest_cards_html = _render_homepage_mosaic_html(blocks, gallery_images_by_category)
            body_replacements['<div class="hp-top-tile" id="hpTopTile"></div>'] = (
                f'<div class="hp-top-tile" id="hpTopTile">{first_tile_html}</div>'
            )
            body_replacements['<div class="hp-mosaic-grid" id="hpMosaic"></div>'] = (
                f'<div class="hp-mosaic-grid" id="hpMosaic">{rest_cards_html}</div>'
            )

            # Uvodni text homepage (Robert primo: "pridej editovatelny text
            # na homepage vcetne meta popisu") - jednoduchy app_settings
            # radek (viz api/cms_blocks.py::admin_homepage_intro_text_*),
            # AZ POD celou mozaikou (SEO substance pod vizualni castí).
            # Prazdne (Robert jeste nenapsal) = cely blok se schova, zadny
            # prazdny ramecek na strance.
            intro_html = (get_setting(cur, "homepage_intro_html", "") or "").strip()
            if _w:
                intro_html = _w.prelozit_nastaveni("homepage_intro_html", intro_html, "html")
            body_replacements['<div class="hp-intro-text" id="hpIntroText"></div>'] = (
                f'<div class="hp-intro-text" id="hpIntroText">{intro_html}</div>' if intro_html else ""
            )

            cur.execute("SELECT * FROM announcement_items WHERE is_visible=1 ORDER BY created_at DESC, id DESC LIMIT 3")
            announcement_items = cur.fetchall()
            body_replacements['<div class="announcement-preview-row" id="announcementPreviewRow"></div>'] = (
                f'<div class="announcement-preview-row" id="announcementPreviewRow">{_render_announcement_preview_html(announcement_items)}</div>'
            )
            if blocks:
                def _hp_block_url(b):
                    if not b.get("gallery_preview"):
                        return f"/blok/{b['slug']}"
                    cat = b.get("gallery_category")
                    return f"/realizace.html?category={quote(cat)}" if cat else "/realizace.html"

                item_list_ld = {
                    "@context": "https://schema.org",
                    "@type": "ItemList",
                    "itemListElement": [
                        {
                            "@type": "ListItem", "position": i + 1,
                            "name": b["title"],
                            "url": f"{PUBLIC_BASE_URL}{_hp_block_url(b)}",
                        }
                        for i, b in enumerate(blocks)
                    ],
                }
                extra_head = _ld_json_script(item_list_ld)
    finally:
        conn.close()
    return _render_og_page("index.html", og, extra_head, body_replacements)

@app.get("/")
def index_root_page():
    return _index_page_response()

@app.get("/index.html")
def index_html_page():
    return _index_page_response()

@app.get("/blok/<slug>")
def homepage_block_page(slug):
    # Robert 2026-08-09 ("funkce jakoby mala web stranka zmensena, kde
    # lze menit nazev, meta popis, obrazek, telo textu") - vlastni
    # samostatna stranka jedne dlazdice homepage mozaiky, se skutecnym
    # title/meta description pro SEO (AskUserQuestion: "Vlastní stránka
    # pro každou dlaždici").
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            og = _get_og_site_defaults(cur)
            cur.execute("SELECT * FROM homepage_blocks WHERE slug=%s AND is_visible=1", (slug,))
            block = cur.fetchone()
            if not block:
                return Response("Stránka nenalezena.", status=404, mimetype="text/plain")
            og["title"] = f"{block['title']} – Hliníkový konstrukční stavebnicový systém s drážkami"
            og["description"] = block["meta_description"] or og["description"]
            og["canonical"] = f"{PUBLIC_BASE_URL}/blok/{block['slug']}"
            if block.get("image_filename"):
                og["image"] = f"/content-files/homepage-blocks/{block['image_filename']}"

            body_replacements = {
                '<span id="breadcrumbTitle"></span>': f'<span id="breadcrumbTitle">{_og_escape(block["title"])}</span>',
            }
            # Robert 2026-08-11 ("kdyz kliknu na dlazdici jakoukoli, než
            # se otevre detail, problikne levé menu jakoze zmizi, nebo
            # se zabali a zase roztáhne") - #catTree tu byl (na rozdil
            # od index.html/category.html/product.html) CISTE
            # klientsky-JS (loadCategoryNav() v blok.html), takze se
            # sidebar pri kazdem otevreni /blok/<slug> nejdriv vykreslil
            # PRAZDNY (jen nadpis, zadne kategorie -> nizky box) a az po
            # dobehnuti fetch("/api/categories") "vyskocil" na plnou
            # vysku - presne to "zabaleni a roztazeni". Stejny SSR fix
            # jako u _index_page_response/_category_page_response.
            _add_category_tree_ssr(cur, body_replacements)
            img_html = (
                f'<div class="block-image-wrap"><img src="{_og_escape(og["image"])}" alt="{_og_escape(block["title"])}"></div>'
                if block.get("image_filename") else ""
            )
            article_html = (
                f'<h1 class="block-title">{_og_escape(block["title"])}</h1>'
                f'{img_html}'
                f'<div class="block-body">{block["body_html"] or ""}</div>'
            )
            body_replacements['<div class="block-not-found">Načítám…</div>'] = article_html
    finally:
        conn.close()
    return _render_og_page("blok.html", og, "", body_replacements)

@app.get("/category.html")
def category_html_page():
    return _category_page_response(request.args.get("id"))

@app.get("/kategorie/<slug>")
def category_html_page_by_slug(slug):
    # STARY tvar URL (SEO audit 2026-08-03). Robert 2026-09-24 pres bot3,
    # doslova: "v URL přece nechceme slovo kategorie!!!" - kanonicky tvar
    # je ted korenovy /<slug> (viz category_html_page_by_root_slug nize).
    # Tahle routa uz JEN 301-presmerovava na korenovy tvar, at stare
    # indexovane/prolinkovane /kategorie/<slug> adresy nedostanou 404
    # (Google penalizuje mizici indexovane stranky vic nez presmerovane).
    # Funguje i pro MEZITIM prejmenovany slug - jde primo na korenovy tvar
    # NOVEHO slugu, ne na /kategorie/<novy> (to by byl zbytecny druhy skok
    # pres tuhle stejnou routu).
    zobraz_skryte = _category_tree_show_hidden()
    conn = get_conn()
    target_slug = None
    try:
        with conn.cursor() as cur:
            if zobraz_skryte:
                cur.execute("SELECT slug FROM content_categories WHERE slug=%s", (slug,))
            else:
                cur.execute(
                    "SELECT slug FROM content_categories WHERE slug=%s AND is_visible=1",
                    (slug,),
                )
            row = cur.fetchone()
            if row:
                target_slug = row["slug"]
            else:
                cur.execute(
                    "SELECT c.slug AS new_slug FROM content_category_redirects r "
                    "JOIN content_categories c ON c.id = r.category_id WHERE r.old_slug=%s",
                    (slug,),
                )
                rr = cur.fetchone()
                if rr:
                    target_slug = rr["new_slug"]
    finally:
        conn.close()
    if not target_slug:
        return Response("Kategorie nenalezena.", status=404, mimetype="text/plain")
    return redirect(f"/{target_slug}", code=301)

@app.get("/<slug>")
def category_html_page_by_root_slug(slug):
    # Kanonicky (korenovy) tvar URL kategorie - Robert 2026-09-24 pres
    # bot3: "v URL přece nechceme slovo kategorie!!!". Predtim
    # /kategorie/<slug> (ted uz jen 301 vyse, pro stare odkazy). Filtr
    # viditelnosti + presmerovani na prejmenovany slug - stejna logika,
    # jakou drive mela /kategorie/<slug>, jen cilovy tvar bez prefixu.
    #
    # POZOR poradi rout: musi zustat AZ PO vsech specifictejsich cestach
    # (/produkt/, /kategorie/, /blok/, /panel/, /category.html, ...) -
    # Werkzeug dava static prefixum prednost pred <slug> bez ohledu na
    # poradi v souboru, ale citelnosti/bezpecnosti pro pristi editaci
    # pomaha mit tuhle routu na konci. Nezachyti vicesegmentove cesty
    # (/produkt/x) - <slug> converter neprejde pres "/".
    zobraz_skryte = _category_tree_show_hidden()
    conn = get_conn()
    redirect_target = None
    try:
        with conn.cursor() as cur:
            if zobraz_skryte:
                cur.execute("SELECT id FROM content_categories WHERE slug=%s", (slug,))
            else:
                cur.execute(
                    "SELECT id FROM content_categories WHERE slug=%s AND is_visible=1",
                    (slug,),
                )
            row = cur.fetchone()
            if not row:
                # Slug byl v adminu zmenen (viz categories_update) - 301 na
                # aktualni URL, at Google/uzivatel nedostane 404 na drive
                # indexovanou/prolinkovanou adresu.
                cur.execute(
                    "SELECT c.slug AS new_slug FROM content_category_redirects r "
                    "JOIN content_categories c ON c.id = r.category_id WHERE r.old_slug=%s",
                    (slug,),
                )
                rr = cur.fetchone()
                if rr:
                    redirect_target = rr["new_slug"]
    finally:
        conn.close()
    if not row:
        if redirect_target:
            return redirect(f"/{redirect_target}", code=301)
        return Response("Kategorie nenalezena.", status=404, mimetype="text/plain")
    return _category_page_response(row["id"])

@app.get("/<slug>/")
def category_html_page_by_root_slug_trailing_slash(slug):
    # Robert primo, 2026-09-30 (presmerovani stareho logiman.cz/Shoptet na
    # nas web) - Shoptet vyzaduje, aby cilova URL presmerovani KONCILA
    # lomitkem ("/stary-blog/" -> "https://cil.cz/"), ale nas kanonicky
    # tvar /<slug> (vyse) lomitko na konci NEMA a Flask/Werkzeug bez
    # explicitni druhe routy vrati na "/<slug>/" 404 (strict_slashes je
    # jednosmerne - jen z bez-lomitka na s-lomitkem, ne obracene). Cisty
    # 301 na kanonicky tvar bez lomitka - zadna duplicitni logika, jen
    # normalizace, existujici /<slug> pak spravne vyresi zbytek (existuje/
    # prejmenovano/404).
    return redirect(f"/{slug}", code=301)

@app.get("/robots.txt")
def robots_txt():
    base = PUBLIC_BASE_URL
    # Vyloucene stranky (SEO audit 2026-08-03): admin panel, interni skener
    # (capture.html), 3D scena (vyzaduje login - viz /api/categories
    # komentar "jen samotna 3D scena a administrace zustavaji za loginem"),
    # a prihlasovaci/registracni tok - zadna z nich nema smysl v indexu
    # vyhledavace (stejny princip jako konkurence do-dodavky.cz, ktera
    # zakazuje /cart, /checkout, /payments). Kategorie/produkty s ?id=
    # ZAMERNE NEjsou zakazany - canonical tag uz rika Googlu, kterou verzi
    # preferovat, a Disallow by mu zabranil canonical vubec videt.
    disallow = [
        "/admin.html", "/capture.html", "/scene.html",
        "/login.html", "/register.html", "/forgot-password.html", "/reset-password.html",
        "/api/",
    ]
    body = "User-agent: *\n" + "".join(f"Disallow: {p}\n" for p in disallow) + f"\nSitemap: {base}/sitemap.xml\n"
    return Response(body, mimetype="text/plain")

@app.get("/sitemap.xml")
def sitemap_xml():
    # <lastmod>/<priority> na kazde URL (SEO audit 2026-08-03, parita s
    # konkurencnim do-dodavky.cz, ktery je ma tez) - kategorie maji vlastni
    # updated_at (viz sql/2026-08-03_category_updated_at.sql), produkty
    # pouzivaji shoptet_updated_at s fallbackem na created_at.
    base = PUBLIC_BASE_URL
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, parent_id, slug, is_visible, updated_at FROM content_categories")
            rows = cur.fetchall()
            cur.execute(
                "SELECT id, slug, COALESCE(shoptet_updated_at, created_at) AS lastmod "
                "FROM shop_products WHERE active=1 AND is_archived=0"
            )
            products = cur.fetchall()
            # Stranky dlazdic homepage (/blok/<slug>, vlastni title/meta
            # description) - v sitemape dosud chybely (bot15, 2026-09-02).
            cur.execute("SELECT slug, updated_at FROM homepage_blocks WHERE is_visible=1 AND gallery_preview=0 AND slug<>'' ORDER BY sort_order, id")
            hp_blocks = cur.fetchall()

            # Otocny nahled (bot16, api/turntable.py) - SEO rozsireni
            # (bot3, 2026-09-02, bod c): u produktu se sadou pridat
            # <image:image> pro 4 KANONICKE snimky (hero/bok/zezadu/shora
            # - jednotlive uhly), NE pro 360 prstencovych snimku a NE pro
            # hero_1x1/hero_16x9 (to jsou jen orezy stejne hero fotky pro
            # OG/JSON-LD, ne dalsi uhel - viz AGENTS_LOG.md). Predfiltr na
            # produkty, ktere vubec MAJI aktivni snimky, at se
            # turntable_public_info() nevola pro cely katalog.
            import turntable
            cur.execute("SELECT DISTINCT shop_product_id FROM product_turntable_frames WHERE is_active=1")
            tt_product_ids = {r["shop_product_id"] for r in cur.fetchall()}
            tt_images_by_product = {}
            for tt_pid in tt_product_ids:
                info = turntable.turntable_public_info(cur, tt_pid)
                canon = info.get("canonical") or {}
                imgs = [canon[k] for k in ("hero", "side", "back", "top") if canon.get(k)]
                if imgs:
                    tt_images_by_product[tt_pid] = imgs
    finally:
        conn.close()
    by_parent = {}
    for r in rows:
        by_parent.setdefault(r["parent_id"], []).append(r)
    cats = []

    def walk(parent_id):
        for r in by_parent.get(parent_id, []):
            if not r["is_visible"]:
                continue
            if r["slug"]:
                cats.append(r)
            walk(r["id"])

    walk(None)

    def _entry(loc, lastmod, priority, images=None):
        xml = f"  <url><loc>{_og_escape(loc)}</loc>"
        if lastmod:
            xml += f"<lastmod>{lastmod.date().isoformat()}</lastmod>"
        xml += f"<priority>{priority}</priority>"
        for img_url in (images or []):
            abs_img = img_url if img_url.startswith("http") else base + img_url
            xml += f"<image:image><image:loc>{_og_escape(abs_img)}</image:loc></image:image>"
        xml += "</url>\n"
        return xml

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n'
    )
    body += _entry(f"{base}/", None, "1.0")
    # Verejne staticke stranky (webapp/*.html, indexovatelne, s vlastnim
    # canonical/OG) - QA seo.py SEO_INDEXABLE_PAGE_NOT_IN_SITEMAP (bot15,
    # 2026-09-02). remeslo*.html sem NEPATRI (aplikace, noindex).
    webapp_dir = os.path.join(os.path.dirname(__file__), "..", "webapp")
    for static_name in ("kontakt.html", "realizace.html"):
        try:
            static_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(webapp_dir, static_name)))
        except OSError:
            static_mtime = None
        body += _entry(f"{base}/{static_name}", static_mtime, "0.5")
    for hb in hp_blocks:
        body += _entry(f"{base}/blok/{hb['slug']}", hb.get("updated_at"), "0.7")
    for c in cats:
        body += _entry(f"{base}/{c['slug']}", c.get("updated_at"), "0.8")
    for p in products:
        body += _entry(f"{base}{_product_rel_url(p)}", p.get("lastmod"), "0.6", images=tt_images_by_product.get(p["id"]))
    body += "</urlset>\n"
    return Response(body, mimetype="application/xml; charset=utf-8")

# --- Strom kategorii (neomezena hloubka) nad 3D scenou i v eshopu ---
# Obecny "resource center" + produktovy katalog v jednom (rozhodnuti
# 2026-07-23, rozsireni na 3 urovne 2026-07-25, pak SJEDNOCENI 2026-07-25
# "chci sjednotit kategorie, oddelit sklad polozek, a zobrazit vse
# navenek" -> "jeden strom, produkty i obsah spolu"). Kazda kategorie muze
# mit VLASTNI OBSAH (content_pages: titulek/telo/video + content_files +
# diskuze) A ZAROVEN produkty (shop_products.category_id odkazuje sem).
# Limit hloubky byl zrusen - produktove kategorie prevzate ze skladapp
# jdou az 4 urovne hluboko (Spojovaci material > Srouby > Metricke > DIN
# 933), umely strop uz nedaval smysl.
def _category_depth(cur, cat_id):
    # Hloubka kategorie v patře (0 = korenova kategorie, 1 = podkategorie,
    # 2 = podpodkategorie). Prochazi retezec parent_id smerem nahoru;
    # ochrana pres "seen" pro pripad cyklu v datech.
    depth = 0
    current = cat_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        cur.execute("SELECT parent_id FROM content_categories WHERE id=%s", (current,))
        row = cur.fetchone()
        if not row or row["parent_id"] is None:
            break
        depth += 1
        current = row["parent_id"]
    return depth

def _category_ancestor_chain(cur, cat_id):
    # Vraci retezec [koren, ..., cat_id] pro drobecky (BreadcrumbList).
    #
    # Vykonnostni audit bot5 2026-09-03 (schvaleno bot3/Robert): puvodne
    # WHILE smycka s 1 SELECTem NA KAZDOU uroven stromu - volana na
    # KAZDE produktove i kategoriove SSR strance, produkcni DB je
    # vzdalena (~21-25ms RTT/dotaz), takze to bylo 2-3 dotazy navic na
    # kazde zobrazeni (119 kategorii, max hloubka 3). Ted jeden dotaz na
    # CELY strom (malo radku) + pruchod k predkum v Pythonu - stejna
    # "seen" ochrana proti cyklum jako drive.
    cur.execute("SELECT id, parent_id, name, slug FROM content_categories")
    by_id = {r["id"]: r for r in cur.fetchall()}
    chain = []
    current = cat_id
    seen = set()
    while current is not None and current not in seen:
        seen.add(current)
        row = by_id.get(current)
        if not row:
            break
        chain.append({"id": row["id"], "name": row["name"], "slug": row["slug"]})
        current = row["parent_id"]
    chain.reverse()
    return chain

def _groove_badges_html(groove_family, cross_section, escape_fn):
    # bot5 2026-08-10 (Robert: "uhelniky nemaji zobaky, takze pasuji na
    # libovolnou drazku, dej jim vsechny 3 ikony") - groove_family muze
    # byt CSV vice hodnot ("6,8,10") u prislusenstvi bez fyzicke vazby
    # na konkretni sirku drazky - vykresli JEDEN <div> odznak za KAZDOU
    # hodnotu (misto jednoho odznaku s jednou barvou). Pouzito v SSR
    # (_category_page_response) - klientsky ekvivalent viz grooveBadgesHtml()
    # v category.html/product.html, MUSI zustat synchronni (viz
    # check_ssr_client_render_drift v api/qa_checks.py).
    if not groove_family:
        return ""
    html = ""
    for g in str(groove_family).split(","):
        g = g.strip()
        if not g:
            continue
        cls = f"groove-badge groove-badge-{g}" if g in ("6", "8", "10") else "groove-badge"
        html += (
            f'<div class="{cls}">⬡ Slot {escape_fn(g)}mm'
            + (f' · {escape_fn(cross_section)}' if cross_section else '')
            + '</div>'
        )
    return html

_THREAD_IN_NAME_RE = re.compile(r"(?<![A-Za-z0-9])M(\d{1,2})(?!\d)")

def _thread_badge_html(name, escape_fn):
    # Robert 2026-08-11 ("vsem produktum ktere uvadeji ze obsahuji zavit
    # tzn nektery z techto znaku, M4, M5, M6, M8, udelej jim ikonu
    # zavitu viditelnou stejne jako ikonu Slotu... napric prislusenstvi
    # a spoj prvku, musi to byt prvek se zavitem") - velikost zavitu se
    # cte primo z nazvu produktu (prvni "M<cislo>" nenavazujici na jine
    # pismeno/cislici: "M6", "M8x20" -> M8, "30x60 M10" -> M10), zadny
    # novy sloupec v DB - overeno 2026-08-11 na vsech 129 aktivnich
    # produktech s "M<cislo>" v nazvu, vse realne zavitove prvky, zadne
    # falesne shody. Klientsky ekvivalent threadBadgeHtml() v
    # category.html/product.html, MUSI zustat synchronni (viz
    # check_ssr_client_render_drift v api/qa_checks.py).
    m = _THREAD_IN_NAME_RE.search(name or "")
    if not m:
        return ""
    return f'<div class="thread-badge">◎ Závit M{escape_fn(m.group(1))}</div>'

# Robert pres bot3, 2026-09-25 (pravidlo 52): graficke stitky "hlavni
# profil" a "strana auta (umisteni)" - zamena leve/prave "stravil
# hodiny", L/P MUSI byt poznat i bez cteni (orientace ikony, ne jen
# pismeno). Klientsky ekvivalent UMISTENI_BADGE_DATA/umisteniBadgeHtml()
# v category.html/product.html, MUSI zustat synchronni (viz
# check_ssr_client_render_drift v api/qa_checks.py) - stejna cisla
# rect/barvy/popisky, stejne poradi SVG elementu.
_UMISTENI_BADGE_DATA = {
    "RL": {"short": "Levá", "rect": (1.5, 3.3, 5.5, 9.2)},
    "RP": {"short": "Pravá", "rect": (11, 3.3, 5.5, 9.2)},
    "RK": {"short": "Kabina", "rect": (1.5, 3.3, 15, 3.2)},
    "DP": {"short": "Dvojitá podlaha", "rect": (1.5, 10.3, 15, 2.2)},
    "VZ": {"short": "Výsuv – zadní dveře", "rect": (5.5, 10.3, 7, 2.2)},
    "VB": {"short": "Výsuv – boční dveře", "rect": (11, 5.5, 5.5, 5)},
    "VP": {"short": "Výsuvná podlaha", "rect": (1.5, 8, 15, 4.5)},
}

def _umisteni_badge_html(kod, nazev, escape_fn):
    d = _UMISTENI_BADGE_DATA.get(kod)
    if not d:
        return ""
    rx, ry, rw, rh = d["rect"]
    return (
        f'<div class="umisteni-badge umisteni-badge-{kod}" title="{escape_fn(nazev or d["short"])}">'
        '<svg viewBox="0 0 18 14" width="18" height="14" aria-hidden="true">'
        '<rect x="1" y="1" width="16" height="12" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/>'
        '<rect x="6" y="1" width="6" height="1.6" fill="currentColor" opacity="0.55"/>'
        f'<rect x="{rx}" y="{ry}" width="{rw}" height="{rh}" fill="currentColor"/>'
        f'</svg><span>{escape_fn(d["short"])}</span></div>'
    )

def _profil_badge_html(mm, escape_fn):
    # Chybejici hodnota (dokud vandr_hlavni_prurez_mm/profil_mm neni u
    # dane karty vyplnene) = zadny stitek, ne "null"/prazdna plaketa -
    # stejne jako profilBadgeHtml() na klientovi.
    if not mm:
        return ""
    val = escape_fn(str(mm))
    return f'<div class="profil-badge">{val}×{val}</div>'

@app.get("/panel/<slug>")
def sidebar_block_page(slug):
    # Vlastni SEO stranka jednoho panelu (viz duvod u /blok/<slug>
    # vyse) - navic VideoObject JSON-LD, kdyz ma panel nahrane video
    # (Google rich results + GEO/AI vyhledavace).
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            og = _get_og_site_defaults(cur)
            cur.execute("SELECT * FROM sidebar_blocks WHERE slug=%s AND is_visible=1", (slug,))
            block = cur.fetchone()
            if not block:
                return Response("Stránka nenalezena.", status=404, mimetype="text/plain")
            og["title"] = f"{block['title']} – Hliníkový konstrukční stavebnicový systém s drážkami"
            og["description"] = block["meta_description"] or og["description"]
            og["canonical"] = f"{PUBLIC_BASE_URL}/panel/{block['slug']}"
            image_url = None
            if block.get("image_filename"):
                image_url = f"{PUBLIC_BASE_URL}/content-files/sidebar-blocks/{block['image_filename']}"
                og["image"] = image_url

            body_replacements = {
                '<span id="breadcrumbTitle"></span>': f'<span id="breadcrumbTitle">{_og_escape(block["title"])}</span>',
            }
            # Robert 2026-08-11 ("problikne levé menu") - viz stejny
            # komentar u /blok/<slug> nize/vyse (_add_category_tree_ssr).
            _add_category_tree_ssr(cur, body_replacements)
            video_url = None
            extra_head = ""
            if block.get("video_filename"):
                video_url = f"{PUBLIC_BASE_URL}/content-files/sidebar-blocks-video/{block['video_filename']}"
                video_ld = {
                    "@context": "https://schema.org",
                    "@type": "VideoObject",
                    "name": block["title"],
                    "description": block["meta_description"] or block["title"],
                    "thumbnailUrl": image_url or video_url,
                    "contentUrl": video_url,
                    "uploadDate": block["created_at"].date().isoformat() if block.get("created_at") else None,
                }
                extra_head = _ld_json_script({k: v for k, v in video_ld.items() if v is not None})
            video_html = (
                f'<div class="block-image-wrap"><video controls preload="none" playsinline '
                f'{"poster=\"" + _og_escape(image_url) + "\"" if image_url else ""} style="width:100%;max-width:480px;display:block;">'
                f'<source src="{_og_escape(video_url)}" type="video/mp4"></video></div>'
                if video_url else ""
            )
            img_html = (
                f'<div class="block-image-wrap"><img src="{_og_escape(image_url)}" alt="{_og_escape(block["title"])}"></div>'
                if image_url and not video_url else ""
            )
            article_html = (
                f'<h1 class="block-title">{_og_escape(block["title"])}</h1>'
                f'{video_html}{img_html}'
                f'<div class="block-body">{block["body_html"] or ""}</div>'
            )
            body_replacements['<div class="block-not-found">Načítám…</div>'] = article_html
    finally:
        conn.close()
    return _render_og_page("blok.html", og, extra_head, body_replacements)

def _render_category_tree_html(tree, active_id=None, expanded_ids=None, depth=0):
    # SSR ekvivalent klientskeho buildCatTreeNode() v category.html/
    # index.html (Robert: "nasad kategoricky strom strukturalne po vzoru
    # Bazarai", stejny vzor jako _render_category_tree_html na
    # vybaveni-uzitkovych-vozidel/api/app.py). Levy strom kategorii byl
    # dosud jen JS-only (#catTree prazdne v syrovem HTML) - pri kazde
    # navigaci (cele nacteni stranky, zadne SPA) se tedy na chvili
    # vyprazdnil a znovu naplnil, viditelny "problik" celeho leveho
    # panelu. Stejna HTML struktura (tridy cat-tree-node/-row/-toggle/
    # -name/-children), at ji JS po nacteni prepise beze zmeny chovani -
    # jen misto span+onclick pouzivame rovnou <a href>, aby strom fungoval
    # (a byl indexovatelny) i pred/bez JS.
    # bot16, 2026-09-17 (Robert pres bot7, screenshot leveho menu: "s tim
    # stejnym podkladem tmava to je spatne pro orientaci cloveka") -
    # `depth` -> data-depth atribut (CSS v kazdem webapp/*.html odliseni
    # hloubky podkladem/levym okrajem, viz .cat-tree-node[data-depth]).
    # `menu_group_label` (content_categories, datove rizeny, ne hardcoded
    # ID v kodu) -> cistě vizualni nadpis PRED timhle uzlem, ne odkaz.
    #
    # DOPLNENO (bot16, 2026-09-17, nalez bot7/Robert po prvnim nasazeni):
    # nestaci vytisknout nadpis JEN kdyz je vyplneny - sourozenci PO
    # oznackovanem uzlu (bez vlastniho menu_group_label) se vizualne tise
    # priradili pod predchozi nadpis, i kdyz tam koncepcne nepatri (233/
    # 260/244/278 pod 184 vypadaly jako soucast "PODLE VOZIDLA"). Misto
    # "tiskni popisek kdyz existuje" proto detekujeme HRANICI SKUPINY
    # mezi sousednimi sourozenci (prev_group sleduje efektivni skupinu
    # PREDCHOZIHO sourozence, None = zadna) - kdykoli se zmeni (i zpet na
    # None), vlozi se oddelovac: s textem, pokud novy uzel skupinu ma,
    # nebo jen tenka linka bez textu, pokud se vraci do neoznackovaneho
    # shluku (at nepusobi jako fantomovy nadpis "None"/prazdny text).
    expanded_ids = expanded_ids or set()
    html = ""
    prev_group = None
    for cat in tree:
        children = cat.get("children") or []
        has_children = bool(children)
        expanded = has_children and cat["id"] in expanded_ids
        toggle_cls = "cat-tree-toggle" + ("" if has_children else " spacer")
        toggle_txt = "−" if expanded else "+"
        name_cls = "cat-tree-name" + (" active" if active_id is not None and cat["id"] == active_id else "") + (" cat-tree-name-new" if cat.get("pending_review") else "")
        group_label = cat.get("menu_group_label")
        if group_label != prev_group:
            marker_html = (
                f'<div class="cat-tree-group-label">{_og_escape(group_label)}</div>'
                if group_label else '<div class="cat-tree-group-break"></div>'
            )
            prev_group = group_label
        else:
            marker_html = ""
        # bot16, 2026-09-17 (Robert primo: "podbarvit otevrenou celou vetev") -
        # SSR MUSI vydat "is-open" rovnou (ne az JS po nacteni) - stejna trida
        # jako buildCatTreeNode() v kazdem webapp/*.html, jinak zpocatku
        # rozbalena vetev (podle expanded_ids/aktivni kategorie) nema na
        # prvni vykresleni zadne podbarveni, jen po rucnim kliku.
        node_cls = "cat-tree-node" + (" is-open" if expanded else "")
        html += (
            f'{marker_html}'
            f'<div class="{node_cls}" data-depth="{depth}">'
            f'<div class="cat-tree-row"><span class="{toggle_cls}">{toggle_txt}</span>'
            f'<a class="{name_cls}" href="{_category_rel_url(cat)}">{_og_escape(cat["name"])}</a></div>'
            f'<div class="cat-tree-children{" expanded" if expanded else ""}">'
            f'{_render_category_tree_html(children, active_id, expanded_ids, depth + 1)}'
            '</div></div>'
        )
    return html

def _add_category_tree_ssr(cur, body_replacements, active_id=None, expanded_ids=None):
    # Sdileny SSR blok pro strom kategorii v levem sidebaru - jediny
    # zdroj teto logiky pro VSECHNY 4 stranky se sidebarem
    # (index/category/product/blok.html+panel). Puvodne mela
    # index.html/category.html kazda svou vlastni rucne psanou kopii a
    # product.html/blok.html/panel jeste nemely SSR vubec (cistě
    # klientsky-JS render az po nacteni stranky) - presne to
    # zpusobovalo "problikne levé menu... zabalí a zase roztáhne"
    # (Robert 2026-08-11), nalezene a opravene postupne pro kazdou
    # stranku, nakonec sjednocene sem, aby dalsi nova stranka se
    # sidebarem nemohla znovu zapomenout.
    #
    # data-ssr="1" marker: klientsky JS (renderCategoryTree v kazdem
    # webapp/*.html) tenhle atribut kontroluje a kdyz je pritomen,
    # PRESKOCI svuj vlastni fetch+prekresleni stromu - jinak i pri
    # 100% identickem vysledku DOM prepis restartuje CSS animaci
    # podtrzeni aktivni/hover polozky (.cat-tree-name::after
    # catTreeShimmer), coz je viditelny "problik podtrzitka" i kdyz se
    # samotny text/struktura stromu vubec nezmeni.
    full_tree = _build_category_tree(cur, _category_tree_show_hidden())
    _w = _wi()
    if _w:
        _w.lokalizuj_strom(full_tree)
    body_replacements['<div class="cat-tree" id="catTree"></div>'] = (
        f'<div class="cat-tree" id="catTree" data-ssr="1">{_render_category_tree_html(full_tree, active_id, expanded_ids or set())}</div>'
    )
    if not full_tree:
        body_replacements[
            '<div class="cat-empty" id="catTreeEmpty" style="display:none;">Zatím tu nejsou žádné kategorie.</div>'
        ] = '<div class="cat-empty" id="catTreeEmpty">Zatím tu nejsou žádné kategorie.</div>'

