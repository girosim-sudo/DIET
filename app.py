"""
Ferrero Mensa Coach - Alba
Web app Streamlit per scegliere il pranzo alla mensa Ferrero Alba e suggerire la cena
in base al piano alimentare personale da 1800 kcal.

Avvio:
    pip install -r requirements.txt
    streamlit run app.py
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup

MENU_INDEX_URL = "https://ferrero.compasscloud.it/presentazione_menu"
APP_DIR = Path(__file__).resolve().parent
LOG_PATH = APP_DIR / "diario_alimentare.json"
APP_VERSION = "0.4.0"

# Preferenze e vincoli personali. Modificabili qui o nel pannello laterale.
DEFAULT_PROFILE = {
    "target_kcal": 1800,
    "acqua_litri": 2.5,
    "olio_g_giorno": 30,
    "verdura_g_pasto": 200,
    "evita": ["fragole", "arachidi"],
    "non_graditi": ["carciofi", "cavolfiore", "broccoli", "melone"],
    "note": [
        "steatosi/MASLD: preferire piatti semplici, verdure, legumi, cereali integrali, pesce e carni magre",
        "niente pane se già si sceglie pasta, riso, farro, cous cous o patate",
        "una sola fonte proteica principale per pasto, salvo porzioni molto piccole",
        "olio: misurato; se il piatto è già condito, non aggiungere altro olio a crudo",
        "peperoncino ok, ma limitarlo se compare reflusso",
    ],
}


# Regole pratiche di rotazione settimanale.
# Sono volutamente conservative: servono a evitare ripetizioni e a spingere pesce/legumi
# quando nella settimana sono rimasti bassi. Sono modificabili in base alle indicazioni della nutrizionista.
WEEKLY_RULES = {
    "fish": {"label": "Pesce", "min": 2, "max": 4, "prefer_if_low": True},
    "legumes": {"label": "Legumi", "min": 2, "max": 4, "prefer_if_low": True},
    "poultry": {"label": "Carne bianca", "min": 0, "max": 5, "prefer_if_low": False},
    "red_meat": {"label": "Carne rossa/maiale", "min": 0, "max": 2, "prefer_if_low": False},
    "cheese": {"label": "Formaggi", "min": 0, "max": 2, "prefer_if_low": False},
    "eggs": {"label": "Uova", "min": 0, "max": 2, "prefer_if_low": False},
    "rich": {"label": "Piatti ricchi", "min": 0, "max": 1, "prefer_if_low": False},
}

FIXED_OPTIONS = [
    {
        "name": "Pokè controllata: riso Venere o farro + 3 verdure + pollo/tacchino + poca salsa yogurt",
        "category": "Piatto unico",
        "line": "Alternative fisse",
        "score": 96,
        "tags": ["carboidrato", "proteina magra", "verdura", "controllabile", "integrale"],
        "reason": "Molto controllabile: carboidrato, proteina magra, tante verdure e condimento moderato.",
    },
    {
        "name": "Pasta integrale al sugo rosso + pollo/tacchino ai ferri + insalata cruda",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 93,
        "tags": ["integrale", "sugo semplice", "proteina magra", "verdura"],
        "reason": "Scelta standard ottima quando il menù del giorno è troppo ricco.",
    },
    {
        "name": "Riso integrale al sugo rosso + pollo/tacchino ai ferri + insalata cruda",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 91,
        "tags": ["integrale", "sugo semplice", "proteina magra", "verdura"],
        "reason": "Alternativa valida alla pasta integrale, saziante e facile da gestire.",
    },
    {
        "name": "Pollo o tacchino ai ferri + verdure crude/cotte + pane controllato",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 89,
        "tags": ["proteina magra", "verdura", "carboidrato controllato"],
        "reason": "Piano B pulito se non ci sono primi o piatti unici adatti.",
    },
    {
        "name": "Sottofiletto ai ferri + insalata grande + pane/riso controllato",
        "category": "Combinazione",
        "line": "Alternative fisse",
        "score": 78,
        "tags": ["carne rossa", "verdura", "occasionale"],
        "reason": "Accettabile, ma meno frequente rispetto a pollo e tacchino perché è carne rossa.",
    },
]

CATEGORY_HEADINGS = {
    "primi piatti": "Primi Piatti",
    "secondi piatti": "Secondi Piatti",
    "contorni": "Contorni",
    "piatto unico": "Piatto unico",
    "alternative fisse": "Alternative fisse",
}

BAD_KEYWORDS = {
    "fritto": -35, "fritti": -35, "chips": -35, "impan": -25, "crosta": -18,
    "gratin": -22, "burro": -20, "panna": -22, "gorgo": -25, "gorgonzola": -25,
    "scamorza": -18, "torta salata": -26, "strudel": -20, "bacon": -28,
    "salsiccia": -30, "salame": -30, "wurstel": -30, "carbonara": -28,
    "nocina": -22, "lasagne": -18, "ragu": -8, "ragù": -8, "maionese": -25,
    "patate fritte": -45, "dolce": -35, "dessert": -35,
}

GOOD_KEYWORDS = {
    "integral": 15, "vapore": 22, "grigliat": 16, "ferri": 20, "sugo rosso": 12,
    "pomodoro": 10, "verdure": 12, "insalata": 18, "bieta": 12, "zucchine": 12,
    "carote": 10, "fagiolini": 12, "cime di rapa": 12, "melanzane": 10,
    "legumi": 18, "ceci": 18, "lenticchie": 18, "fagioli": 18, "piselli": 11,
    "pesce": 18, "tonno": 18, "nasello": 20, "orata": 20, "passera": 20,
    "sgombro": 15, "salmone": 12, "trota": 10, "pollo": 18, "tacchino": 18,
    "farro": 15, "riso venere": 17, "riso integrale": 17, "basmati": 8,
    "quinoa": 16, "cous cous": 10, "zuppa": 8, "minestrone": 12,
}

PROTEIN_KEYWORDS = {
    "fish": ["pesce", "tonno", "salmone", "sgombro", "trota", "orata", "nasello", "passera", "merluzzo", "platessa", "gamberi"],
    "poultry": ["pollo", "tacchino"],
    "red_meat": ["bovino", "vitello", "manzo", "sottofiletto", "tagliata", "lonza", "maiale"],
    "eggs": ["uova", "frittata"],
    "cheese": ["ricotta", "primo sale", "mozzarella", "fiocchi", "scamorza", "gorgo", "formaggio"],
    "legumes": ["ceci", "lenticchie", "fagioli", "piselli", "legumi", "falafel"],
    "soy": ["tofu", "seitan", "soia"],
}

CARB_KEYWORDS = ["pasta", "riso", "farro", "orzo", "cous cous", "quinoa", "pane", "patate", "lasagne", "noodles", "spaghetti", "fusilli", "penne", "pennette", "rigatoni", "tagliatelle"]
VEG_KEYWORDS = ["verdure", "insalata", "zucchine", "carote", "bieta", "fagiolini", "broccoli", "cavolfiore", "cime di rapa", "melanzane", "pomodoro", "pomodorini", "asparagi", "songino", "crudite", "crudité", "agro", "spinaci"]
RICH_KEYWORDS = ["frit", "gratin", "burro", "panna", "gorgo", "scamorza", "torta salata", "strudel", "bacon", "salsiccia", "lasagne", "crosta", "impan", "nocina"]

@dataclass
class Dish:
    name: str
    category: str = "Altro"
    line: str = ""
    score: int = 0
    tags: List[str] = None
    reason: str = ""
    url: str = ""

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def lower(text: str) -> str:
    return normalize(text).lower()


def is_probable_dish(line: str) -> bool:
    if not line or len(line) < 4:
        return False
    lowered = lower(line)
    banned_exact = {
        "visualizza", "tutti", "pranzo", "cena", "stampa il menu", "precedente", "successiva",
        "caricamento in corso...", "il tuo menu", "completa settimana", "visualizza piatti senza:",
        "le immagini visualizzate sono a puro titolo esemplificativo",
    }
    if lowered in banned_exact:
        return False
    if lowered.startswith("image:") or lowered.startswith("cereali contenenti"):
        return False
    if "prodotti a base" in lowered or "allerg" in lowered:
        return False
    if lowered.startswith("giu ") or re.match(r"^(lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica)$", lowered):
        return False
    if lowered in CATEGORY_HEADINGS:
        return False
    if lowered.startswith("linea self") or lowered.startswith("primavera"):
        return False
    return any(k in lowered for k in CARB_KEYWORDS + VEG_KEYWORDS + sum(PROTEIN_KEYWORDS.values(), []) + ["zuppa", "crema", "burger", "falafel"])


def classify_category(name: str, current_category: Optional[str] = None) -> str:
    n = lower(name)
    if current_category:
        return current_category
    if any(k in n for k in ["pasta", "spaghetti", "fusilli", "penne", "pennette", "rigatoni", "tagliatelle", "risotto", "riso", "zuppa", "crema", "minestrone", "cous cous", "farro", "orzo"]):
        return "Primi Piatti"
    if any(k in n for k in ["pollo", "tacchino", "bovino", "vitello", "lonza", "orata", "nasello", "passera", "salmone", "sgombro", "trota", "uova", "frittata", "burger", "tofu", "seitan", "falafel", "straccetti", "filetto"]):
        return "Secondi Piatti"
    if any(k in n for k in VEG_KEYWORDS) or "patate" in n:
        return "Contorni"
    if any(k in n for k in ["noodles", "nasi goreng", "fish and chips"]):
        return "Piatto unico"
    return "Altro"


def score_dish(name: str, category: str = "Altro", line: str = "") -> Tuple[int, List[str], str]:
    n = lower(name)
    score = 50
    tags: List[str] = []
    reasons: List[str] = []

    if "healthy" in lower(line):
        score += 8
        tags.append("linea healthy")
    if "urban" in lower(line):
        score -= 3
    if "traditional" in lower(line):
        score -= 2

    for kw, delta in GOOD_KEYWORDS.items():
        if kw in n:
            score += delta
            tags.append(kw)
    for kw, delta in BAD_KEYWORDS.items():
        if kw in n:
            score += delta
            tags.append(f"attenzione: {kw}")

    if category == "Contorni":
        score += 10
        if "patate" in n:
            score -= 12
            tags.append("patate = carboidrato")
        if any(k in n for k in ["gratin", "fritte", "burro"]):
            score -= 25
    elif category == "Primi Piatti":
        score += 2
        if any(k in n for k in ["integral", "farro", "orzo", "riso venere", "riso integrale"]):
            score += 8
        if any(k in n for k in ["ricotta", "pesto", "crema", "caprese"]):
            score -= 5
    elif category == "Secondi Piatti":
        score += 5
        if any(k in n for k in ["vapore", "ferri", "grigli"]):
            score += 15
        if any(k in n for k in ["lonza", "bovino", "vitello", "maiale", "sottofiletto"]):
            score -= 5
    elif category == "Piatto unico":
        score += 4

    # Allergie dichiarate nel piano: fragole e arachidi.
    if "arachid" in n:
        score = min(score, 5)
        tags.append("evitare: arachidi")
        reasons.append("Contiene arachidi, da evitare per allergia/intolleranza indicata.")
    if "fragol" in n:
        score = min(score, 5)
        tags.append("evitare: fragole")
        reasons.append("Contiene fragole, da evitare per allergia/intolleranza indicata.")

    if any(k in n for k in CARB_KEYWORDS):
        tags.append("carboidrato")
    if any(k in n for k in VEG_KEYWORDS):
        tags.append("verdura")
    for protein_type, kws in PROTEIN_KEYWORDS.items():
        if any(k in n for k in kws):
            tags.append(protein_type)

    if score >= 85:
        reasons.append("Molto adatto: semplice, bilanciabile e coerente con carboidrato/proteina/verdura.")
    elif score >= 70:
        reasons.append("Buono, da completare con verdura e condimento controllato.")
    elif score >= 55:
        reasons.append("Accettabile, ma attenzione ad abbinamenti e porzioni.")
    else:
        reasons.append("Da limitare oggi: rischia di essere troppo ricco o poco adatto all'obiettivo.")

    return max(0, min(100, score)), sorted(set(tags)), " ".join(reasons)


def fetch_url(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; FerreroMensaCoach/1.0; +local-app)",
        "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
    }
    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    return response.text


def get_menu_links() -> Dict[str, str]:
    html = fetch_url(MENU_INDEX_URL)
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    links: Dict[str, str] = {}

    # Strategia robusta: i link "Visualizza" sono preceduti dal nome linea.
    visible_links = [a for a in anchors if "menu/" in a["href"]]
    text_lines = [normalize(x) for x in soup.get_text("\n").split("\n") if normalize(x)]
    line_names = [x for x in text_lines if x.upper().startswith("LINEA SELF ALBA") or "LUNCH BOX" in x.upper()]

    for idx, a in enumerate(visible_links):
        href = a["href"]
        if href.startswith("/"):
            href = "https://ferrero.compasscloud.it" + href
        elif href.startswith("menu/"):
            href = "https://ferrero.compasscloud.it/" + href
        label = line_names[idx] if idx < len(line_names) else f"Linea {idx + 1}"
        if "POZZUOLO" not in label.upper() and "LUNCH BOX" not in label.upper():
            links[label] = href
    return links


def parse_menu_page(url: str) -> Tuple[str, str, List[Dish]]:
    html = fetch_url(url)
    soup = BeautifulSoup(html, "html.parser")
    lines = [normalize(x) for x in soup.get_text("\n").split("\n") if normalize(x)]

    menu_date = next((x for x in lines if re.search(r"\b\d{1,2}\s+\w+\s+20\d{2}\b", x, flags=re.I)), "")
    line_name = next((x for x in lines if x.upper().startswith("LINEA SELF")), "")

    dishes: List[Dish] = []
    current_category: Optional[str] = None
    in_daily = False

    # Tenta estrazione del solo menu giornaliero tra "Il Tuo menu" e "I piatti contrassegnati".
    daily_lines: List[str] = []
    for x in lines:
        xl = lower(x)
        if xl == "il tuo menu":
            in_daily = True
            daily_lines = []
            continue
        if in_daily and xl.startswith("i piatti contrassegnati"):
            break
        if in_daily:
            daily_lines.append(x)

    for x in daily_lines:
        xl = lower(x)
        if xl in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[xl]
            continue
        if is_probable_dish(x):
            cat = classify_category(x, current_category)
            sc, tags, reason = score_dish(x, cat, line_name)
            dishes.append(Dish(name=x, category=cat, line=line_name, score=sc, tags=tags, reason=reason, url=url))

    # Fallback: se il blocco giornaliero non viene estratto bene, usa tutte le righe probabili.
    if not dishes:
        for x in lines:
            xl = lower(x)
            if xl in CATEGORY_HEADINGS:
                current_category = CATEGORY_HEADINGS[xl]
                continue
            if is_probable_dish(x):
                cat = classify_category(x, current_category)
                sc, tags, reason = score_dish(x, cat, line_name)
                dishes.append(Dish(name=x, category=cat, line=line_name, score=sc, tags=tags, reason=reason, url=url))

    # Deduplica preservando ordine.
    seen = set()
    unique: List[Dish] = []
    for d in dishes:
        key = (lower(d.name), d.category, lower(d.line))
        if key not in seen:
            unique.append(d)
            seen.add(key)
    return menu_date, line_name, unique


def load_all_menus(selected_lines: Optional[List[str]] = None, target_date: Optional[date] = None) -> Tuple[str, List[Dish], List[str]]:
    errors: List[str] = []
    all_dishes: List[Dish] = []
    menu_date = ""
    links = get_menu_links()
    if selected_lines:
        links = {k: v for k, v in links.items() if k in selected_lines}
    if target_date is not None:
        links = {k: adjust_menu_url_date(v, target_date) for k, v in links.items()}
    for line_name, url in links.items():
        try:
            d, line, dishes = parse_menu_page(url)
            if d and not menu_date:
                menu_date = d
            # Se il nome linea non viene estratto, usa quello dell'indice.
            for dish in dishes:
                if not dish.line:
                    dish.line = line_name
            all_dishes.extend(dishes)
        except Exception as exc:  # noqa: BLE001 - utile in app locale
            errors.append(f"{line_name}: {exc}")

    # Aggiunge alternative fisse personali.
    for item in FIXED_OPTIONS:
        all_dishes.append(Dish(**item))

    return menu_date, all_dishes, errors


def parse_manual_menu(text: str) -> List[Dish]:
    dishes: List[Dish] = []
    current_category: Optional[str] = None
    for raw in text.splitlines():
        line = normalize(raw.strip("-•* "))
        if not line:
            continue
        xl = lower(line).rstrip(":")
        if xl in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[xl]
            continue
        if ":" in line and lower(line.split(":", 1)[0]) in CATEGORY_HEADINGS:
            current_category = CATEGORY_HEADINGS[lower(line.split(":", 1)[0])]
            rest = line.split(":", 1)[1].strip()
            if rest:
                for part in re.split(r"[,;]", rest):
                    p = normalize(part)
                    if p:
                        cat = classify_category(p, current_category)
                        sc, tags, reason = score_dish(p, cat, "Menu manuale")
                        dishes.append(Dish(p, cat, "Menu manuale", sc, tags, reason))
            continue
        if is_probable_dish(line) or len(line.split()) >= 2:
            cat = classify_category(line, current_category)
            sc, tags, reason = score_dish(line, cat, "Menu manuale")
            dishes.append(Dish(line, cat, "Menu manuale", sc, tags, reason))
    for item in FIXED_OPTIONS:
        dishes.append(Dish(**item))
    return dishes


def unique_dishes(dishes: Iterable[Dish]) -> List[Dish]:
    seen = set()
    out = []
    for d in dishes:
        key = (lower(d.name), d.category)
        if key not in seen:
            out.append(d)
            seen.add(key)
    return out


def best_by_category(dishes: List[Dish], category: str, n: int = 5) -> List[Dish]:
    return sorted([d for d in dishes if d.category == category], key=lambda d: d.score, reverse=True)[:n]


def find_best_lunch(dishes: List[Dish], weekly_counts_data: Optional[Dict[str, int]] = None) -> Dict[str, object]:
    dishes = unique_dishes(apply_weekly_balance(dishes, weekly_counts_data))
    piatti_unici = sorted([d for d in dishes if d.category in {"Piatto unico", "Combinazione"}], key=lambda d: d.score, reverse=True)
    primi = best_by_category(dishes, "Primi Piatti", 10)
    secondi = best_by_category(dishes, "Secondi Piatti", 10)
    contorni = best_by_category(dishes, "Contorni", 10)

    candidates: List[Dict[str, object]] = []

    for d in piatti_unici[:8]:
        candidates.append({
            "type": "piatto_unico",
            "score": d.score,
            "items": [d],
            "text": d.name,
            "rationale": d.reason,
        })

    for primo in primi[:6]:
        for secondo in secondi[:6]:
            # Evita doppia proteina se il primo contiene già tonno/salmone/uova/formaggio/legumi.
            primo_has_protein = any(tag in primo.tags for tag in ["fish", "poultry", "red_meat", "eggs", "cheese", "legumes", "soy"])
            penalty = 14 if primo_has_protein else 0
            contorno = contorni[0] if contorni else None
            combo_score = int((primo.score * 0.36) + (secondo.score * 0.38) + ((contorno.score if contorno else 60) * 0.26) - penalty)
            items = [primo, secondo] + ([contorno] if contorno else [])
            candidates.append({
                "type": "combo",
                "score": combo_score,
                "items": items,
                "text": " + ".join(d.name for d in items),
                "rationale": "Combinazione completa: carboidrato + proteina + verdura. " + ("Attenzione: il primo contiene già una proteina; evita porzioni doppie. " if primo_has_protein else ""),
            })

    # Primo proteico + contorno senza secondo.
    for primo in primi[:8]:
        if any(tag in primo.tags for tag in ["fish", "eggs", "cheese", "legumes", "soy", "poultry"]):
            contorno = contorni[0] if contorni else None
            combo_score = int((primo.score * 0.68) + ((contorno.score if contorno else 60) * 0.32) + 4)
            items = [primo] + ([contorno] if contorno else [])
            candidates.append({
                "type": "primo_proteico",
                "score": combo_score,
                "items": items,
                "text": " + ".join(d.name for d in items),
                "rationale": "Il primo contiene già una proteina: non aggiungere pane né un secondo completo.",
            })

    # Secondo + contorno + carboidrato semplice quando i primi non sono adatti.
    for secondo in secondi[:8]:
        contorno = contorni[0] if contorni else None
        combo_score = int((secondo.score * 0.58) + ((contorno.score if contorno else 60) * 0.32) + 8)
        text = f"{secondo.name} + {contorno.name if contorno else 'insalata cruda'} + pane/riso controllato"
        items = [secondo] + ([contorno] if contorno else [])
        candidates.append({
            "type": "secondo_contorno",
            "score": combo_score,
            "items": items,
            "text": text,
            "rationale": "Usa una sola quota di carboidrato: pane oppure riso/pasta semplice, non entrambi.",
        })

    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    best = candidates[0] if candidates else None
    alternatives = candidates[1:4]
    avoid = sorted([d for d in dishes if d.score < 55], key=lambda d: d.score)[:8]
    return {"best": best, "alternatives": alternatives, "avoid": avoid, "all": dishes}


def meal_contains(items: Iterable[Dish], words: Iterable[str]) -> bool:
    text = " ".join(d.name for d in items).lower()
    return any(w in text for w in words)


def suggest_dinner(lunch_items: Iterable[Dish], lunch_score: int, weekly_counts_data: Optional[Dict[str, int]] = None) -> Dict[str, str]:
    items = list(lunch_items)
    rich = meal_contains(items, RICH_KEYWORDS) or lunch_score < 65
    fish = meal_contains(items, PROTEIN_KEYWORDS["fish"])
    poultry = meal_contains(items, PROTEIN_KEYWORDS["poultry"])
    red_meat = meal_contains(items, PROTEIN_KEYWORDS["red_meat"])
    cheese = meal_contains(items, PROTEIN_KEYWORDS["cheese"])
    legumes = meal_contains(items, PROTEIN_KEYWORDS["legumes"])
    eggs = meal_contains(items, PROTEIN_KEYWORDS["eggs"])
    carb_heavy = meal_contains(items, ["lasagne", "patate", "pizza", "pasta", "riso", "cous cous", "farro", "noodles"])

    if rich:
        dinner = "Cena leggera: pollo/tacchino ai ferri o pesce bianco + verdure abbondanti. Carboidrato ridotto: 50-70 g pane oppure niente pane se non hai fame."
        why = "Il pranzo è risultato ricco o poco pulito: la sera compensiamo senza saltare il pasto."
    elif fish:
        dinner = "Cena: pollo o tacchino ai ferri + verdure abbondanti + 80-100 g pane fresco/integrale. Evita formaggi e salumi."
        why = "A pranzo hai già usato pesce/tonno/salmone: la sera ruotiamo su carne bianca magra."
    elif red_meat:
        dinner = "Cena: pesce bianco al forno/vapore oppure legumi + verdure + 80-100 g pane. Evita altra carne rossa."
        why = "A pranzo c'è carne rossa: meglio non ripeterla nello stesso giorno."
    elif cheese:
        dinner = "Cena: pesce bianco o tacchino + verdure + 80-100 g pane. Niente altri formaggi."
        why = "A pranzo c'è formaggio: la sera conviene scegliere una proteina più magra."
    elif legumes:
        dinner = "Cena: pesce o pollo/tacchino + verdure + pane controllato. Se hai gonfiore, evita altri legumi la sera."
        why = "A pranzo hai già inserito legumi: ottimo, ma meglio variare la proteina a cena."
    elif eggs:
        dinner = "Cena: pesce bianco o pollo/tacchino + verdure + pane controllato. Evita altre uova."
        why = "A pranzo hai già usato uova: ruotiamo la fonte proteica."
    elif poultry:
        dinner = "Cena: pesce oppure legumi + verdure + pane/riso controllato."
        why = "A pranzo hai fatto carne bianca: la sera si può variare con pesce o legumi."
    else:
        dinner = "Cena: proteina magra a scelta + verdure abbondanti + 80-100 g pane o 80 g riso."
        why = "Pranzo abbastanza neutro: resta sullo schema base del piano."

    if weekly_counts_data and not rich:
        low_fish = weekly_counts_data.get("fish", 0) < WEEKLY_RULES["fish"]["min"]
        low_legumes = weekly_counts_data.get("legumes", 0) < WEEKLY_RULES["legumes"]["min"]
        high_red = weekly_counts_data.get("red_meat", 0) >= WEEKLY_RULES["red_meat"]["max"]
        high_cheese = weekly_counts_data.get("cheese", 0) >= WEEKLY_RULES["cheese"]["max"]
        high_eggs = weekly_counts_data.get("eggs", 0) >= WEEKLY_RULES["eggs"]["max"]

        if low_fish and not fish:
            dinner = "Cena preferita oggi: pesce semplice al forno/vapore/padella antiaderente + verdure abbondanti + 80-100 g pane."
            why += " Bilanciamento settimanale: il pesce è ancora basso, quindi oggi conviene inserirlo."
        elif low_legumes and not legumes and not eggs:
            dinner = "Cena preferita oggi: legumi (ceci/lenticchie/fagioli) + verdure + una quota controllata di pane, riso o farro."
            why += " Bilanciamento settimanale: i legumi sono ancora bassi, quindi oggi conviene recuperarli."
        if high_red:
            why += " Carne rossa già al limite: evita carne cruda, sottofiletto, vitello, lonza e ragù a cena."
        if high_cheese:
            why += " Formaggi già al limite: evita feta, mozzarella, ricotta, primo sale e scamorza a cena."
        if high_eggs:
            why += " Uova già al limite: evita frittata o uova a cena."

    if carb_heavy and not rich:
        why += " Poiché a pranzo c'è già una quota di carboidrati, a cena non sommare pane e patate/riso."
    return {"dinner": dinner, "why": why}


def load_log() -> List[Dict[str, object]]:
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_log(entries: List[Dict[str, object]]) -> None:
    LOG_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def add_log_entry(entry: Dict[str, object]) -> None:
    entries = load_log()
    entries.append(entry)
    save_log(entries)


def dedupe_entries(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    output: List[Dict[str, object]] = []
    for e in entries:
        key = (str(e.get("date", "")), str(e.get("breakfast", "")), str(e.get("lunch", "")), str(e.get("dinner", "")))
        if key not in seen:
            output.append(e)
            seen.add(key)
    output.sort(key=lambda x: str(x.get("date", "")))
    return output


def render_diary_tools(entries: List[Dict[str, object]]) -> None:
    with st.sidebar.expander("Backup diario"):
        st.caption("Su Streamlit il file locale può non essere eterno. Esporta il diario ogni tanto e reimportalo se serve.")
        st.download_button(
            "Scarica diario JSON",
            data=json.dumps(entries, ensure_ascii=False, indent=2),
            file_name="diario_alimentare_ferrero.json",
            mime="application/json",
            use_container_width=True,
        )
        uploaded = st.file_uploader("Importa diario JSON", type=["json"], label_visibility="collapsed")
        col_a, col_b = st.columns(2)
        with col_a:
            if uploaded is not None and st.button("Unisci", use_container_width=True):
                try:
                    imported = json.loads(uploaded.getvalue().decode("utf-8"))
                    if not isinstance(imported, list):
                        raise ValueError("Il file non contiene una lista di giornate.")
                    save_log(dedupe_entries(entries + imported))
                    st.success("Diario importato e unito. Ricarica la pagina se non vedi subito i dati.")
                except Exception as exc:
                    st.error(f"Import non riuscito: {exc}")
        with col_b:
            if uploaded is not None and st.button("Sostituisci", use_container_width=True):
                try:
                    imported = json.loads(uploaded.getvalue().decode("utf-8"))
                    if not isinstance(imported, list):
                        raise ValueError("Il file non contiene una lista di giornate.")
                    save_log(dedupe_entries(imported))
                    st.success("Diario sostituito. Ricarica la pagina se non vedi subito i dati.")
                except Exception as exc:
                    st.error(f"Import non riuscito: {exc}")


def categories_in_text(text: str) -> set[str]:
    """Riconosce le categorie proteiche e i piatti ricchi in un testo libero."""
    t = lower(text)
    found: set[str] = set()
    for key, kws in PROTEIN_KEYWORDS.items():
        if key == "soy":
            continue
        if any(k in t for k in kws):
            found.add(key)
    if any(k in t for k in RICH_KEYWORDS):
        found.add("rich")
    return found


def weekly_counts(entries: List[Dict[str, object]], reference_date: Optional[date] = None) -> Dict[str, int]:
    """Conta le fonti proteiche negli ultimi 7 giorni, distinguendo pranzo e cena.

    La versione precedente contava la categoria al massimo una volta al giorno; questa versione
    conta pranzo e cena separatamente, così il bilanciamento è più realistico.
    """
    counts = {"fish": 0, "poultry": 0, "red_meat": 0, "cheese": 0, "eggs": 0, "legumes": 0, "rich": 0}
    today = reference_date or date.today()
    for e in entries:
        try:
            d = datetime.fromisoformat(str(e.get("date"))).date()
        except Exception:
            continue
        delta = (today - d).days
        if delta < 0 or delta > 6:
            continue
        for field in ("lunch", "dinner"):
            cats = categories_in_text(str(e.get(field, "")))
            for cat in cats:
                if cat in counts:
                    counts[cat] += 1
    return counts


def weekly_balance_messages(counts: Dict[str, int]) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    fish = counts.get("fish", 0)
    legumes = counts.get("legumes", 0)
    red_meat = counts.get("red_meat", 0)
    cheese = counts.get("cheese", 0)
    eggs = counts.get("eggs", 0)
    rich = counts.get("rich", 0)

    if fish < WEEKLY_RULES["fish"]["min"]:
        messages.append({"level": "info", "text": "Pesce basso nella settimana: se possibile oggi privilegia pesce semplice o tonno non troppo spesso."})
    if legumes < WEEKLY_RULES["legumes"]["min"]:
        messages.append({"level": "info", "text": "Legumi bassi nella settimana: buona idea inserirli a pranzo o cena."})
    if red_meat >= WEEKLY_RULES["red_meat"]["max"]:
        messages.append({"level": "warning", "text": "Carne rossa già alta: oggi evita sottofiletto, lonza, vitello, ragù e carne cruda."})
    elif red_meat == 1:
        messages.append({"level": "info", "text": "Hai già una quota di carne rossa: usala solo se il resto del menù è scarso."})
    if cheese >= WEEKLY_RULES["cheese"]["max"]:
        messages.append({"level": "warning", "text": "Formaggi già al limite: oggi evita feta, primo sale, mozzarella, ricotta, scamorza e gorgonzola."})
    elif cheese == 1:
        messages.append({"level": "info", "text": "Hai già fatto formaggio: meglio non ripeterlo oggi se ci sono alternative."})
    if eggs >= WEEKLY_RULES["eggs"]["max"]:
        messages.append({"level": "warning", "text": "Uova già al limite: oggi evita frittata/uova e ruota su pesce, legumi o carne bianca."})
    if rich > WEEKLY_RULES["rich"]["max"]:
        messages.append({"level": "warning", "text": "Settimana un po' ricca: evita fritti, gratin, salse, lasagne e formaggi pesanti."})
    if not messages:
        messages.append({"level": "success", "text": "Rotazione settimanale equilibrata: scegli il piatto migliore del giorno senza forzature."})
    return messages


def weekly_adjustment_for_dish(dish: Dish, counts: Dict[str, int]) -> Tuple[int, List[str]]:
    text = lower(dish.name + " " + " ".join(dish.tags))
    cats = categories_in_text(text)
    adjustment = 0
    notes: List[str] = []

    if "fish" in cats:
        if counts.get("fish", 0) < WEEKLY_RULES["fish"]["min"]:
            adjustment += 10
            notes.append("bonus settimanale: pesce da inserire")
        elif counts.get("fish", 0) >= WEEKLY_RULES["fish"]["max"]:
            adjustment -= 8
            notes.append("pesce già frequente")
    if "legumes" in cats:
        if counts.get("legumes", 0) < WEEKLY_RULES["legumes"]["min"]:
            adjustment += 14
            notes.append("bonus settimanale: legumi da inserire")
        elif counts.get("legumes", 0) >= WEEKLY_RULES["legumes"]["max"]:
            adjustment -= 5
            notes.append("legumi già frequenti")
    if "red_meat" in cats:
        if counts.get("red_meat", 0) >= WEEKLY_RULES["red_meat"]["max"]:
            adjustment -= 30
            notes.append("penalità: carne rossa già al limite")
        elif counts.get("red_meat", 0) == 1:
            adjustment -= 12
            notes.append("carne rossa già presente in settimana")
    if "cheese" in cats:
        if counts.get("cheese", 0) >= WEEKLY_RULES["cheese"]["max"]:
            adjustment -= 30
            notes.append("penalità: formaggi già al limite")
        elif counts.get("cheese", 0) == 1:
            adjustment -= 12
            notes.append("formaggio già presente in settimana")
    if "eggs" in cats:
        if counts.get("eggs", 0) >= WEEKLY_RULES["eggs"]["max"]:
            adjustment -= 24
            notes.append("penalità: uova già al limite")
        elif counts.get("eggs", 0) == 1:
            adjustment -= 8
            notes.append("uova già presenti in settimana")
    if "poultry" in cats and counts.get("poultry", 0) >= WEEKLY_RULES["poultry"]["max"]:
        adjustment -= 8
        notes.append("carne bianca già molto frequente")
    if "rich" in cats and counts.get("rich", 0) >= WEEKLY_RULES["rich"]["max"]:
        adjustment -= 20
        notes.append("settimana già ricca")

    return adjustment, notes


def apply_weekly_balance(dishes: List[Dish], counts: Optional[Dict[str, int]]) -> List[Dish]:
    if not counts:
        return dishes
    balanced: List[Dish] = []
    for d in dishes:
        adjustment, notes = weekly_adjustment_for_dish(d, counts)
        new_score = max(0, min(100, d.score + adjustment))
        reason = d.reason
        tags = list(d.tags)
        if notes:
            reason += " Bilanciamento settimanale: " + "; ".join(notes) + "."
            tags.extend(notes)
        balanced.append(Dish(
            name=d.name,
            category=d.category,
            line=d.line,
            score=new_score,
            tags=sorted(set(tags)),
            reason=reason,
            url=d.url,
        ))
    return balanced


def render_weekly_sidebar(entries: List[Dict[str, object]], selected_date: date) -> Dict[str, int]:
    counts = weekly_counts(entries, selected_date)
    st.sidebar.divider()
    st.sidebar.header("Bilanciamento 7 giorni")
    for key in ["fish", "legumes", "poultry", "red_meat", "cheese", "eggs", "rich"]:
        rule = WEEKLY_RULES.get(key, {})
        label = rule.get("label", key)
        value = counts.get(key, 0)
        max_value = int(rule.get("max", 4))
        min_value = int(rule.get("min", 0))
        if key in {"fish", "legumes"} and value < min_value:
            icon = "🟡"
        elif value > max_value or (key in {"red_meat", "cheese", "eggs", "rich"} and value >= max_value):
            icon = "🔴"
        else:
            icon = "🟢"
        st.sidebar.write(f"{icon} {label}: **{value}**")
    for msg in weekly_balance_messages(counts):
        if msg["level"] == "warning":
            st.sidebar.warning(msg["text"])
        elif msg["level"] == "success":
            st.sidebar.success(msg["text"])
        else:
            st.sidebar.info(msg["text"])
    return counts


def render_score(score: int) -> str:
    if score >= 85:
        return f"🟢 {score}/100"
    if score >= 70:
        return f"🟡 {score}/100"
    if score >= 55:
        return f"🟠 {score}/100"
    return f"🔴 {score}/100"



BREAKFAST_OPTIONS = [
    "Pane + velo marmellata + latte parzialmente scremato",
    "Yogurt bianco magro + cereali senza zuccheri",
    "Caffè/cappuccino + brioche",
    "Solo caffè / colazione saltata",
    "Altro",
]


def format_it_date(d: date) -> str:
    weekdays = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    months = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    return f"{weekdays[d.weekday()]} {d.day} {months[d.month - 1]} {d.year}"


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def adjust_menu_url_date(url: str, target_date: date) -> str:
    """CompassCloud usa nel path /menu/<timestamp>/...; il timestamp cresce di 86400 al giorno.
    Parto dal link corrente letto dalla pagina indice e lo traslo alla data selezionata.
    Se il sito cambia struttura, ritorno il link originale.
    """
    match = re.search(r"/menu/(\d{10})/", url)
    if not match:
        return url
    ts = int(match.group(1))
    base_dt = datetime.fromtimestamp(ts)
    delta_days = (target_date - base_dt.date()).days
    new_ts = ts + (delta_days * 86400)
    return url.replace(f"/menu/{ts}/", f"/menu/{new_ts}/")


def evaluate_breakfast(choice: str, custom: str = "") -> Dict[str, str]:
    text = lower(choice + " " + custom)
    if "saltata" in text or "solo caff" in text:
        return {
            "level": "warning",
            "title": "Colazione troppo leggera",
            "message": "Meglio evitare di arrivare a pranzo troppo affamato: oggi scegli un pranzo ordinato e non compensare con pane/dolci extra.",
        }
    if "brioche" in text:
        return {
            "level": "warning",
            "title": "Colazione più ricca",
            "message": "Va considerata come extra rispetto allo schema: a pranzo resta su sugo semplice, proteina magra e verdura, senza pane aggiunto.",
        }
    if "yogurt" in text or "cereali" in text:
        return {
            "level": "success",
            "title": "Colazione molto coerente",
            "message": "Buona base: proteine leggere, carboidrati controllati e buona sazietà. Mantieni normale il pranzo.",
        }
    if "pane" in text or "latte" in text:
        return {
            "level": "success",
            "title": "Colazione coerente",
            "message": "Scelta in linea con il piano. A pranzo puoi seguire normalmente carboidrato + proteina + verdura.",
        }
    return {
        "level": "info",
        "title": "Colazione registrata",
        "message": "Valutala in modo pratico: se è stata ricca, alleggerisci i condimenti; se è stata scarsa, non compensare con scelte impulsive.",
    }


def dishes_from_free_text(text: str) -> List[Dish]:
    text = normalize(text)
    if not text:
        return []
    parts = [normalize(x) for x in re.split(r"\s\+\s|;|\n", text) if normalize(x)]
    dishes: List[Dish] = []
    for part in parts or [text]:
        cat = classify_category(part)
        sc, tags, reason = score_dish(part, cat, "Inserito")
        dishes.append(Dish(part, cat, "Inserito", sc, tags, reason))
    return dishes


def suggest_dinner_alternatives(lunch_items: Iterable[Dish], lunch_score: int, weekly_counts_data: Optional[Dict[str, int]] = None) -> List[Dict[str, str]]:
    items = list(lunch_items)
    fish = meal_contains(items, PROTEIN_KEYWORDS["fish"])
    poultry = meal_contains(items, PROTEIN_KEYWORDS["poultry"])
    red_meat = meal_contains(items, PROTEIN_KEYWORDS["red_meat"])
    cheese = meal_contains(items, PROTEIN_KEYWORDS["cheese"])
    legumes = meal_contains(items, PROTEIN_KEYWORDS["legumes"])
    eggs = meal_contains(items, PROTEIN_KEYWORDS["eggs"])
    rich = meal_contains(items, RICH_KEYWORDS) or lunch_score < 65

    pool = []
    if not fish:
        pool.append({
            "title": "Pesce semplice",
            "plate": "Merluzzo/nasello/orata al forno o in padella antiaderente + verdure abbondanti + 80-100 g pane.",
            "why": "Ottimo per variare le proteine e restare leggero.",
        })
    if not poultry:
        pool.append({
            "title": "Carne bianca",
            "plate": "Pollo o tacchino ai ferri + insalata grande o verdure cotte + 80-100 g pane fresco/integrale.",
            "why": "Scelta pulita quando il pranzo è stato ricco o incerto.",
        })
    if not legumes and not rich:
        pool.append({
            "title": "Legumi",
            "plate": "Lenticchie/ceci/fagioli + verdure + una piccola quota di farro/riso o pane controllato.",
            "why": "Aiuta a ridurre la frequenza di carne e formaggi nella settimana.",
        })
    if not eggs and not rich:
        pool.append({
            "title": "Uova",
            "plate": "Frittata al forno con 2 uova e spinaci/zucchine + insalata + pane controllato.",
            "why": "Alternativa semplice, purché non ci siano già state uova a pranzo.",
        })
    if not red_meat and not rich:
        pool.append({
            "title": "Carne cruda piemontese",
            "plate": "Carne cruda di bovino/Fassona 150-170 g + insalata grande + 80-100 g pane. Poco olio, limone/pepe a piacere.",
            "why": "Può rientrare come tradizione e piatto proteico pulito, senza aggiungere formaggi o altri secondi.",
        })
    if cheese:
        pool.append({
            "title": "Cena senza formaggi",
            "plate": "Pesce bianco o tacchino + verdure + pane controllato. Evita mozzarella, feta, primo sale e salumi.",
            "why": "A pranzo c'è già stata quota formaggio: meglio non ripeterla.",
        })

    if weekly_counts_data:
        def option_priority(opt: Dict[str, str]) -> int:
            title = lower(opt.get("title", ""))
            plate = lower(opt.get("plate", ""))
            text = title + " " + plate
            score = 50
            if "pesce" in text:
                score += 18 if weekly_counts_data.get("fish", 0) < WEEKLY_RULES["fish"]["min"] else 0
                score -= 12 if weekly_counts_data.get("fish", 0) >= WEEKLY_RULES["fish"]["max"] else 0
            if "legumi" in text or "ceci" in text or "lenticchie" in text or "fagioli" in text:
                score += 22 if weekly_counts_data.get("legumes", 0) < WEEKLY_RULES["legumes"]["min"] else 0
            if "carne cruda" in text or "sottofiletto" in text or "vitello" in text:
                score -= 30 if weekly_counts_data.get("red_meat", 0) >= WEEKLY_RULES["red_meat"]["max"] else 0
            if "uova" in text or "frittata" in text:
                score -= 25 if weekly_counts_data.get("eggs", 0) >= WEEKLY_RULES["eggs"]["max"] else 0
            if "formagg" in text or "feta" in text or "mozzarella" in text or "primo sale" in text:
                score -= 25 if weekly_counts_data.get("cheese", 0) >= WEEKLY_RULES["cheese"]["max"] else 0
            return score
        pool = sorted(pool, key=option_priority, reverse=True)

    return pool[:4]


def evaluate_dinner_text(dinner_text: str, lunch_text: str = "") -> Dict[str, str]:
    text = lower(dinner_text)
    lunch = lower(lunch_text)
    if not text:
        return {"level": "info", "message": "Inserisci la cena quando l'hai decisa o consumata: l'app la salverà nel diario."}
    warnings = []
    if not any(k in text for k in VEG_KEYWORDS):
        warnings.append("manca una verdura evidente")
    if any(k in text for k in RICH_KEYWORDS):
        warnings.append("ci sono elementi ricchi: fritti/gratin/salse/formaggi pesanti")
    if any(k in text for k in PROTEIN_KEYWORDS["red_meat"]) and any(k in lunch for k in PROTEIN_KEYWORDS["red_meat"]):
        warnings.append("carne rossa sia a pranzo sia a cena")
    if any(k in text for k in PROTEIN_KEYWORDS["cheese"]) and any(k in lunch for k in PROTEIN_KEYWORDS["cheese"]):
        warnings.append("formaggi ripetuti nello stesso giorno")
    if warnings:
        return {"level": "warning", "message": "Attenzione: " + "; ".join(warnings) + "."}
    return {"level": "success", "message": "Cena registrata: sembra coerente se le porzioni sono controllate e la verdura è abbondante."}


def weekend_suggestions(selected_date: date, breakfast_choice: str, breakfast_custom: str = "", weekly_counts_data: Optional[Dict[str, int]] = None) -> Dict[str, List[Dict[str, str]]]:
    b = lower(breakfast_choice + " " + breakfast_custom)
    light_after_breakfast = "brioche" in b
    lunch = [
        {
            "title": "Pranzo base mediterraneo",
            "plate": "Pasta integrale/riso/farro 80-90 g con sugo rosso + pollo/tacchino o pesce + insalata grande.",
            "why": "È la versione casalinga più vicina alla mensa ideale: carboidrato, proteina e verdura.",
        },
        {
            "title": "Pranzo con legumi",
            "plate": "Farro/riso + ceci/lenticchie/fagioli + verdure crude e cotte. Poco olio, limone/aceto/spezie.",
            "why": "Utile nel weekend per non eccedere con carne, formaggi e affettati.",
        },
        {
            "title": "Carne cruda piemontese",
            "plate": "Carne cruda 150 g + insalata grande + 80-100 g pane. Niente formaggi o salumi nello stesso pasto.",
            "why": "Tradizione compatibile se trattata come fonte proteica principale e non come antipasto extra.",
        },
    ]
    if light_after_breakfast:
        lunch.insert(0, {
            "title": "Dopo brioche: pranzo pulito",
            "plate": "Pesce bianco o tacchino + verdure abbondanti + 70-80 g pane o riso. Evita dolci e formaggi.",
            "why": "La colazione è stata più ricca: a pranzo teniamo il condimento molto semplice.",
        })
    dinner = [
        {
            "title": "Cena pesce",
            "plate": "Pesce al forno/vapore + verdure + 80-100 g pane. Patate solo se non hai già fatto pasta/riso a pranzo.",
            "why": "Scelta equilibrata e molto adatta al weekend.",
        },
        {
            "title": "Cena carne bianca",
            "plate": "Pollo/tacchino ai ferri + verdure cotte/crude + pane controllato.",
            "why": "Semplice, saziante e facile da tenere dentro lo schema.",
        },
        {
            "title": "Cena uova",
            "plate": "Frittata al forno con 2 uova e verdure + insalata. Pane controllato se serve.",
            "why": "Buona alternativa quando a pranzo non hai già usato uova.",
        },
    ]
    if weekly_counts_data:
        def option_score(opt: Dict[str, str]) -> int:
            text = lower(opt.get("title", "") + " " + opt.get("plate", ""))
            score = 50
            if any(k in text for k in ["pesce", "merluzzo", "orata", "nasello"]):
                score += 18 if weekly_counts_data.get("fish", 0) < WEEKLY_RULES["fish"]["min"] else 0
            if any(k in text for k in ["legumi", "ceci", "lenticchie", "fagioli"]):
                score += 22 if weekly_counts_data.get("legumes", 0) < WEEKLY_RULES["legumes"]["min"] else 0
            if any(k in text for k in ["carne cruda", "fassona", "sottofiletto", "vitello"]):
                score -= 35 if weekly_counts_data.get("red_meat", 0) >= WEEKLY_RULES["red_meat"]["max"] else 0
            if any(k in text for k in ["uova", "frittata"]):
                score -= 28 if weekly_counts_data.get("eggs", 0) >= WEEKLY_RULES["eggs"]["max"] else 0
            if any(k in text for k in ["formaggio", "feta", "mozzarella", "primo sale"]):
                score -= 28 if weekly_counts_data.get("cheese", 0) >= WEEKLY_RULES["cheese"]["max"] else 0
            return score
        lunch = sorted(lunch, key=option_score, reverse=True)
        dinner = sorted(dinner, key=option_score, reverse=True)
    return {"lunch": lunch[:4], "dinner": dinner[:3]}


def main() -> None:
    st.set_page_config(page_title="Ferrero Mensa Coach", page_icon="🥗", layout="centered")
    st.title("🥗 Ferrero Mensa Coach - Alba")
    st.markdown("""
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    div[data-testid="stMetricValue"] {font-size: 1.1rem;}
    .stButton button {width: 100%; border-radius: 10px;}
    @media (max-width: 768px) {
        h1 {font-size: 1.6rem !important;}
        h2, h3 {font-size: 1.15rem !important;}
        .block-container {padding-left: 1rem; padding-right: 1rem;}
    }
    </style>
    """, unsafe_allow_html=True)
    st.caption("Supporto pratico per applicare il piano alimentare alla mensa. Non sostituisce nutrizionista o medico.")

    with st.sidebar:
        st.header("Giornata")
        selected_date = st.date_input("Data da pianificare", value=date.today(), format="DD/MM/YYYY")
        if not isinstance(selected_date, date):
            selected_date = date.today()
        st.write(f"**{format_it_date(selected_date)}**")
        st.divider()
        st.header("Profilo")
        st.write(f"Schema: **{DEFAULT_PROFILE['target_kcal']} kcal**")
        st.write(f"Acqua: **{DEFAULT_PROFILE['acqua_litri']} L/die**")
        st.write(f"Olio EVO target: **{DEFAULT_PROFILE['olio_g_giorno']} g/die**")
        st.write("Alternative fisse considerate: pollo/tacchino ai ferri, sottofiletto ai ferri, banco insalata, pasta/riso al sugo rosso, pokè.")
        st.divider()
        mode = st.radio("Origine menù", ["Scarica dal sito", "Inserisco/copio il menù"], index=0)
        include_traditional = st.checkbox("Traditional", value=True)
        include_healthy = st.checkbox("Healthy", value=True)
        include_urban = st.checkbox("Urban Grill", value=True)
        include_chroma = st.checkbox("Chroma Corner", value=False)
        include_local = st.checkbox("Local&World", value=True)
        st.divider()
        st.write("Allergie/intolleranze da evitare: **fragole, arachidi**.")
        st.write("Non graditi: carciofi, cavolfiore, broccoli, melone.")

    entries = load_log()
    weekly_counts_data = render_weekly_sidebar(entries, selected_date)
    render_diary_tools(entries)

    st.subheader("☕ Colazione")
    breakfast_choice = st.selectbox("Cosa hai fatto a colazione?", BREAKFAST_OPTIONS)
    breakfast_custom = ""
    if breakfast_choice == "Altro":
        breakfast_custom = st.text_input("Descrivi la colazione", placeholder="Esempio: latte + Weetabix, yogurt + frutta...")
    breakfast_eval = evaluate_breakfast(breakfast_choice, breakfast_custom)
    getattr(st, breakfast_eval["level"])(f"**{breakfast_eval['title']}** — {breakfast_eval['message']}")

    st.divider()

    if is_weekend(selected_date):
        st.subheader(f"Weekend — {format_it_date(selected_date)}")
        st.info("Sabato e domenica non considero la mensa: ti propongo pranzo e cena da casa/ristorante mantenendo la stessa logica del piano.")
        weekend = weekend_suggestions(selected_date, breakfast_choice, breakfast_custom, weekly_counts_data)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🍽️ Pranzo consigliato")
            for opt in weekend["lunch"]:
                with st.container(border=True):
                    st.markdown(f"**{opt['title']}**")
                    st.write(opt["plate"])
                    st.caption(opt["why"])
        with col2:
            st.markdown("### 🌙 Cena consigliata")
            for opt in weekend["dinner"]:
                with st.container(border=True):
                    st.markdown(f"**{opt['title']}**")
                    st.write(opt["plate"])
                    st.caption(opt["why"])

        st.divider()
        st.markdown("### Diario weekend")
        eaten_lunch = st.text_area("Cosa hai mangiato a pranzo?", placeholder="Esempio: carne cruda + insalata + pane...")
        dinner_input = st.text_area("Cosa hai mangiato o mangerai a cena?", placeholder="Esempio: orata + zucchine + pane...")
        dinner_eval = evaluate_dinner_text(dinner_input, eaten_lunch)
        getattr(st, dinner_eval["level"])(dinner_eval["message"])
        note = st.text_area("Note facoltative", placeholder="Fame, reflusso, acqua bevuta, allenamento...")
        if st.button("Salva giornata weekend"):
            add_log_entry({
                "date": selected_date.isoformat(),
                "breakfast": breakfast_choice if breakfast_choice != "Altro" else breakfast_custom,
                "lunch": eaten_lunch,
                "dinner": dinner_input,
                "score": None,
                "note": note,
            })
            st.success("Giornata salvata nel diario locale.")

        st.caption("Versione 0.4.0 web/mobile. Nel weekend la mensa è esclusa e l'app propone pasti domestici.")
        return

    selected_lines = None
    if mode == "Scarica dal sito":
        try:
            links = get_menu_links()
            selected_lines = []
            for name in links:
                up = name.upper()
                if "TRADITIONAL" in up and include_traditional:
                    selected_lines.append(name)
                elif "HEALTHY" in up and include_healthy:
                    selected_lines.append(name)
                elif "URBAN" in up and include_urban:
                    selected_lines.append(name)
                elif "CHROMA" in up and include_chroma:
                    selected_lines.append(name)
                elif "LOCAL" in up and include_local:
                    selected_lines.append(name)
        except Exception:
            selected_lines = None

    if mode == "Scarica dal sito":
        with st.spinner("Leggo il menù Ferrero CompassCloud..."):
            try:
                menu_date, dishes, errors = load_all_menus(selected_lines=selected_lines, target_date=selected_date)
            except Exception as exc:
                menu_date, dishes, errors = "", [], [str(exc)]
        if errors:
            with st.expander("Avvisi di lettura sito"):
                for e in errors:
                    st.warning(e)
        if not dishes:
            st.error("Non sono riuscito a leggere il sito. Usa la modalità manuale nel pannello laterale e incolla il menù.")
            st.stop()
    else:
        st.info("Incolla il menù: puoi scrivere 'Primi:', 'Secondi:', 'Contorni:' e poi i piatti.")
        manual_text = st.text_area("Menù del giorno", height=220, placeholder="Primi: pasta integrale al pomodoro; risotto...\nSecondi: pollo ai ferri; nasello al vapore...\nContorni: melanzane al funghetto; insalata...")
        dishes = parse_manual_menu(manual_text) if manual_text else [Dish(**item) for item in FIXED_OPTIONS]
        menu_date = selected_date.strftime("%d/%m/%Y")

    result = find_best_lunch(dishes, weekly_counts_data)
    best = result["best"]
    alternatives = result["alternatives"]
    avoid = result["avoid"]

    st.subheader(f"Indicazione per {format_it_date(selected_date)} {('— menù ' + menu_date) if menu_date else ''}")

    if best:
        lunch_items: List[Dish] = best["items"]  # type: ignore[assignment]
        col1, col2 = st.columns([1.2, 1])
        with col1:
            st.markdown("### ✅ Pranzo consigliato")
            st.markdown(f"**{best['text']}**")
            st.markdown(f"Punteggio: **{render_score(int(best['score']))}**")
            st.write(str(best["rationale"]))
            st.info("Regola: niente pane se il pranzo contiene già pasta/riso/farro/cous cous/patate. Aggiungi insalata cruda se la verdura del piatto è poca.")
        with col2:
            st.markdown("### 🌙 Cena: prima indicazione")
            dinner = suggest_dinner(lunch_items, int(best["score"]), weekly_counts_data)
            st.markdown(f"**{dinner['dinner']}**")
            st.write(dinner["why"])
            st.warning("Bevi fino ad arrivare ad almeno 2,5 L d'acqua nella giornata. Peperoncino ok se non dà reflusso.")

        st.divider()
        st.markdown("### Alternative valide per pranzo")
        if alternatives:
            for alt in alternatives:
                with st.container(border=True):
                    st.markdown(f"**{alt['text']}**")
                    st.caption(f"Punteggio: {render_score(int(alt['score']))} — {alt['rationale']}")
        else:
            st.write("Nessuna alternativa rilevante trovata.")

        st.markdown("### Da evitare o limitare oggi")
        if avoid:
            cols = st.columns(2)
            for i, d in enumerate(avoid):
                with cols[i % 2]:
                    st.write(f"{render_score(d.score)} **{d.name}** — {d.line}")
        else:
            st.write("Non emergono piatti chiaramente critici tra quelli letti.")

        st.divider()
        st.markdown("### Cena personalizzata")
        eaten_lunch = st.text_input("Cosa hai mangiato davvero a pranzo?", value=str(best["text"]))
        actual_lunch_items = dishes_from_free_text(eaten_lunch) or lunch_items
        actual_score = int(sum(d.score for d in actual_lunch_items) / max(1, len(actual_lunch_items))) if actual_lunch_items else int(best["score"])
        dinner_recalc = suggest_dinner(actual_lunch_items, actual_score, weekly_counts_data)
        st.markdown(f"**Cena suggerita in base al pranzo inserito:** {dinner_recalc['dinner']}")
        st.caption(dinner_recalc["why"])

        st.markdown("#### Alternative cena")
        for opt in suggest_dinner_alternatives(actual_lunch_items, actual_score, weekly_counts_data):
            with st.container(border=True):
                st.markdown(f"**{opt['title']}**")
                st.write(opt["plate"])
                st.caption(opt["why"])

        dinner_input = st.text_area("Cosa hai mangiato o mangerai a cena?", value=dinner_recalc["dinner"])
        dinner_eval = evaluate_dinner_text(dinner_input, eaten_lunch)
        getattr(st, dinner_eval["level"])(dinner_eval["message"])

        st.divider()
        st.markdown("### Tutti i piatti letti e punteggio")
        for d in sorted(unique_dishes(dishes), key=lambda x: x.score, reverse=True):
            with st.expander(f"{render_score(d.score)} {d.name} — {d.category} — {d.line}"):
                st.write(d.reason)
                if d.tags:
                    st.write("Tag:", ", ".join(d.tags))
                if d.url:
                    st.write(d.url)

        st.divider()
        st.markdown("### Diario")
        note = st.text_area("Note facoltative", placeholder="Fame, reflusso, energia, acqua bevuta...")
        if st.button("Salva giornata"):
            add_log_entry({
                "date": selected_date.isoformat(),
                "breakfast": breakfast_choice if breakfast_choice != "Altro" else breakfast_custom,
                "lunch": eaten_lunch,
                "dinner": dinner_input,
                "score": int(best["score"]),
                "note": note,
            })
            st.success("Giornata salvata nel diario locale.")


    st.caption("Versione 0.4.0 web/mobile. Se CompassCloud cambia struttura, usa la modalità manuale dal menu laterale.")


if __name__ == "__main__":
    main()
