# Ferrero Mensa Coach - Alba

Web app per scegliere il pranzo alla mensa Ferrero Alba e ricevere una proposta di cena coerente con il piano alimentare personale da 1800 kcal.

## Uso previsto

La versione ideale è online: pubblichi l'app su Streamlit Cloud, apri il link dal telefono e lo aggiungi alla schermata Home dell'iPhone.

Per le istruzioni complete di pubblicazione da telefono leggi:

`DEPLOY_MOBILE.md`

## Cosa fa

- Legge il menu pubblico da `https://ferrero.compasscloud.it/presentazione_menu`.
- Considera le linee Alba selezionate: Traditional, Healthy, Urban Grill, Local&World, Chroma Corner.
- Aggiunge le alternative fisse dichiarate: pollo/tacchino ai ferri, sottofiletto ai ferri, banco insalata, pasta/riso al sugo rosso e pokè.
- Valuta i piatti con un sistema di punteggio da 0 a 100.
- Propone il pranzo migliore e alcune alternative.
- Suggerisce la cena in base al pranzo scelto.
- Salva un diario semplice in `diario_alimentare.json` quando usata localmente.
- Ha una modalità manuale se il sito non è raggiungibile o cambia struttura.

## Avvio locale Windows

1. Installa Python 3.10 o superiore.
2. Estrai questa cartella.
3. Apri Prompt dei comandi o PowerShell nella cartella.
4. Esegui:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Avvio locale macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Pubblicazione online

Metodo consigliato:

1. Carica i file su un repository GitHub privato.
2. Pubblica su Streamlit Community Cloud.
3. Apri il link da Safari su iPhone.
4. Aggiungi alla schermata Home.

## Personalizzazione

Nel file `app.py` puoi modificare:

- `DEFAULT_PROFILE`: calorie, acqua, olio, allergie, alimenti non graditi.
- `FIXED_OPTIONS`: alternative sempre disponibili in mensa.
- `GOOD_KEYWORDS` e `BAD_KEYWORDS`: regole di punteggio.
- `suggest_dinner()`: logica della cena.

## Nota importante

L'app è un assistente pratico, non un dispositivo medico. Le indicazioni devono restare coerenti con il piano concordato con la nutrizionista e con eventuali indicazioni del medico.
