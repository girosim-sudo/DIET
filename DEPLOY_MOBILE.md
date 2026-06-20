# Deploy mobile/web su Streamlit Cloud

Questa app è pensata per essere usata da iPhone/iPad come web app.

## 1. Carica i file su GitHub

Nel repository devono esserci almeno:

```text
app.py
requirements.txt
README.md
CHANGELOG.md
```

Consigliato: lascia `app.py` nella cartella principale del repository.

## 2. Streamlit Cloud

Apri Streamlit Community Cloud, collega GitHub e crea una nuova app.

Impostazioni consigliate:

```text
Repository: girosim-sudo/DIET
Branch: main
Main file path: app.py
```

Premi Deploy.

## 3. Aggiornare l'app

Quando carichi una nuova versione su GitHub, Streamlit di solito aggiorna automaticamente.
Se non succede:

- apri la dashboard Streamlit;
- entra nell'app;
- premi Reboot o Redeploy.

## 4. Usarla da iPhone/iPad

Apri il link Streamlit da Safari, poi:

```text
Condividi → Aggiungi a schermata Home
```

## 5. Backup diario

La versione v0.4.0 salva il diario in `diario_alimentare.json` e include anche esportazione/importazione JSON dalla barra laterale.

Su Streamlit Cloud il file locale può non essere permanente se l'app viene riavviata o ridistribuita. Consiglio pratico: ogni 2-3 giorni usa "Scarica diario JSON" dalla barra laterale.
