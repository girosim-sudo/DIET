# Uso quotidiano da telefono: pubblicazione web app

Questa cartella contiene una **web app Streamlit**. Non è una app iOS/Android da installare dall'App Store: si pubblica online e si apre dal telefono con un link.

## Flusso previsto

1. Ogni mattina apri il link dal telefono.
2. L'app legge il menù Ferrero CompassCloud Alba.
3. Ti propone:
   - pranzo consigliato;
   - alternative valide;
   - piatti da evitare/limitare;
   - cena consigliata in base al pranzo.
4. Se il sito non è leggibile, usi la modalità manuale e incolli il menù.

## Pubblicazione consigliata: Streamlit Community Cloud

### 1. Crea un repository GitHub

Nome suggerito: `ferrero-mensa-coach`

Carica nel repository questi file:

- `app.py`
- `requirements.txt`
- `runtime.txt`
- `.streamlit/config.toml`
- `README.md`

Consiglio privacy: usa un repository **privato**, perché il codice contiene preferenze alimentari, allergie e note legate al tuo piano.

### 2. Pubblica su Streamlit Cloud

1. Vai su Streamlit Community Cloud.
2. Accedi con GitHub.
3. Clicca **Create app**.
4. Scegli il repository `ferrero-mensa-coach`.
5. Branch: `main`.
6. Main file path: `app.py`.
7. Deploy.

Alla fine otterrai un link del tipo:

`https://nome-scelto.streamlit.app`

### 3. Mettila sulla schermata Home dell'iPhone

1. Apri il link in Safari.
2. Tocca il pulsante di condivisione.
3. Scegli **Aggiungi a schermata Home**.
4. Nome suggerito: `Mensa Coach`.
5. Tocca **Aggiungi**.

Da quel momento la apri come una normale app.

## Nota su diario e privacy

Il diario salvato dall'app viene scritto in un piccolo file locale dell'ambiente in cui l'app gira. In cloud può non essere stabile nel tempo e non va usato per dati sensibili. Usalo solo per note semplici tipo "ho mangiato pasta + pollo". Se vuoi un diario serio e privato, la versione successiva dovrebbe usare Google Sheets privato o un piccolo database con autenticazione.

## Modalità di emergenza

Se il portale CompassCloud cambia struttura o blocca la lettura automatica, apri il menu laterale e seleziona:

`Inserisco/copio il menù`

Poi incolla i piatti del giorno. L'app continuerà a suggerire pranzo e cena.
