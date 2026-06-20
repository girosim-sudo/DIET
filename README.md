# Ferrero Mensa Coach - Alba

Web app Streamlit per aiutare Simone a scegliere cosa mangiare alla mensa Ferrero di Alba e a bilanciare la cena secondo il piano alimentare personale.

La logica è costruita su uno schema da 1800 kcal con pasti composti da una fonte di carboidrato, una fonte proteica, verdura abbondante e condimento controllato. L'app non sostituisce medico o nutrizionista.

## Funzioni principali

- Lettura del menù Ferrero CompassCloud quando disponibile.
- Modalità manuale se il sito non risponde: puoi incollare il menù.
- Scelta della data.
- Domanda sulla colazione.
- Suggerimento del pranzo migliore in mensa.
- Inserimento del pranzo realmente mangiato.
- Suggerimento della cena in base al pranzo reale.
- Alternative per la cena.
- Sabato e domenica: niente mensa, proposta di pranzo e cena da casa/ristorante.
- Diario alimentare locale.
- Bilanciamento settimanale automatico.
- Backup e import del diario in JSON.

## Novità v0.4.0

L'app ora tiene conto degli ultimi 7 giorni e modifica i consigli in base alla rotazione delle fonti proteiche:

- Se il pesce è basso, dà bonus a pesce semplice e tonno.
- Se i legumi sono bassi, dà bonus a ceci, lenticchie, fagioli e piatti con legumi.
- Se la carne rossa è già alta, penalizza sottofiletto, vitello, lonza, ragù e carne cruda.
- Se i formaggi sono già frequenti, penalizza feta, primo sale, mozzarella, ricotta, scamorza e gorgonzola.
- Se le uova sono già frequenti, penalizza frittata e uova.
- Se la settimana è già ricca, penalizza fritti, gratin, salse, lasagne e piatti molto conditi.

Il conteggio distingue pranzo e cena, quindi se mangi formaggio due volte nello stesso giorno viene contato due volte.

## Uso locale

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy su Streamlit Cloud

Nel repository GitHub assicurati che siano presenti almeno:

```text
app.py
requirements.txt
README.md
```

In Streamlit Cloud imposta:

```text
Repository: girosim-sudo/DIET
Branch: main
Main file path: app.py
```

Poi premi Deploy.

## Aggiornamento da versione precedente

Carica su GitHub almeno questi file aggiornati:

```text
app.py
README.md
CHANGELOG.md
```

Poi su Streamlit fai Reboot o Redeploy se non si aggiorna da solo.

## Nota sul diario

Il diario viene salvato in `diario_alimentare.json`. Su Streamlit Cloud il file locale può non essere permanente in caso di riavvio dell'app. Per questo nella barra laterale è stata aggiunta la sezione "Backup diario": ogni tanto scarica il JSON e reimportalo se serve.
