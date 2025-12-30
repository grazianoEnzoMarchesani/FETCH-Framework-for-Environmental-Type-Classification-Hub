# Report Metodologico: Evoluzione del Classificatore LCZ

Questo documento analizza il passaggio dalla vecchia logica di classificazione a quella attuale, spiegando perché il nuovo approccio non è un "artificio" ma un ritorno al rigore statistico richiesto dal protocollo di Stewart & Oke (2012).

## 1. Il Vecchio Metodo: La Trappola dei "Perfect Matches"

### Come funzionava
Il precedente classificatore utilizzava un sistema gerarchico basato sul conteggio dei **Perfect Matches** (parametri il cui valore cadeva esattamente nel range teorico).

1.  Contava quanti parametri erano "perfetti" per ogni classe.
2.  La classe con il maggior numero di match vinceva.
3.  In caso di parità, si guardava l'RMSEP (l'errore residuo).

### Il difetto logico (L'Anomalia LCZ 10)
Questo approccio era un'approssimazione binaria. Consideriamo una cella di **LCZ 1** (Compatto alto) con questi dati reali:
*   **SVF**: 0.5 (Range LCZ 1: 0.2-0.4 | Range LCZ 10: 0.6-0.9).
*   **Altezza Edifici**: 30m (Range LCZ 1: >25m | Range LCZ 10: 5-15m).

Con l'approccio vecchio, se una cella aveva un SVF di **0.65**:
- Per la **LCZ 10**, questo era un "Match Perfetto" (voto 1).
- Per la **LCZ 1**, era un errore (voto 0).
- Risultato: **Vinceva la LCZ 10**, anche se l'altezza di 30m era totalmente incompatibile (errore enorme). L'algoritmo ignorava la "magnitudo" dell'errore sugli altri parametri pur di premiare il singolo match fortuito.

---

## 2. Il Nuovo Metodo: Distanza dal Profilo Ideale (RMSEP-Driven)

La nuova logica inverte la priorità, passando da una logica "vota chi indovina" a una logica **"vota chi è più vicino al profilo ideale"**.

### La Logica Impeccabile
Abbiamo rimosso la priorità ai Perfect Matches, spostandola sul **RMSEP (Root Mean Square Error Percentage)** globale.

1.  **Analisi di Profilo**: Invece di guardare i singoli parametri come compartimenti stagni, l'algoritmo guarda la cella come un "punto" in uno spazio a 10 dimensioni.
2.  **RMSEP come Metrica di Prossimità**: Calcoliamo quanto la cella dista dal centro geometrico di ogni classe. 
    - Un RMSEP di **0.1** significa che la cella è vicina al 90% al profilo teorico.
    - Un RMSEP di **6.0** (come quello visto nella Classe 10) significa che la cella è fuori strada del 600%. 
3.  **Il Filtro di Sicurezza (Distanza Massima)**: Abbiamo introdotto una soglia di validità. Se l'errore minimo trovato è comunque superiore a **1.0**, la cella viene dichiarata **N/D (Non Classificabile)**. 

---

## 3. Confronto Sintetico

| Caratteristica | Vecchia Logica | Nuova Logica | Rilevanza Scientifica |
| :--- | :--- | :--- | :--- |
| **Priorità** | Match Binario (Dentro/Fuori) | Errore Continuo (RMSEP) | Alta: Premia la coerenza globale. |
| **Gestione LCZ 10** | "Vinceva" per SVF ampio | "Perde" per incoerenza d'altezza | Risolve i falsi positivi industriali. |
| **Robustezza** | Bassa (Sensibile a singoli outlier) | Alta (Media pesata degli errori) | Riduce il "rumore" nel dashboard. |
| **Risultato LCZ 1** | Difficile da centrare | Centrata per coerenza di profilo | Migliora il riconoscimento zone dense. |

## Conclusione
Non è una "pezza". Abbiamo sostituito un **algoritmo decisionale discreto** (che trattava la natura come una serie di interruttori On/Off) con un **modello di prossimità statistica** (che vede la natura come un gradiente).

Questo rende FETCH molto più simile al modo in cui un ricercatore umano analizzerebbe i dati: guardando se il "quadro generale" quadra, non se un singolo numero rientra in una tabella.
