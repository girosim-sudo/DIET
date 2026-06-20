# Changelog

## v0.4.0

### Nuovo
- Aggiunto bilanciamento settimanale automatico negli ultimi 7 giorni.
- L'app ora usa il diario salvato per modificare i punteggi dei piatti: penalizza formaggi, uova e carne rossa se già frequenti; spinge pesce e legumi se sono bassi.
- La cena suggerita ora considera sia il pranzo reale sia la rotazione settimanale.
- Nel weekend le proposte pranzo/cena vengono ordinate anche in base a cosa hai già mangiato in settimana.
- Nuova sezione laterale "Bilanciamento 7 giorni" con semafori e messaggi pratici.
- Nuova sezione "Backup diario": esporta/importa il diario in formato JSON, utile perché su Streamlit il salvataggio locale può non essere permanente.

### Migliorato
- Conteggio settimanale più realistico: pranzo e cena vengono contati separatamente.
- Migliori avvisi su ripetizione di formaggi, uova, carne rossa e piatti ricchi.
- Più coerenza con l'uso pratico da iPad/iPhone.

## v0.3.0
- Scelta della data.
- Domanda sulla colazione.
- Inserimento pranzo reale.
- Cena ricalcolata in base al pranzo.
- Alternative cena.
- Sabato e domenica senza mensa: proposta pranzo/cena.
