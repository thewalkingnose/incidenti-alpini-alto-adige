# Incidenti di soccorso alpino in Alto Adige (2020–2026)

Dashboard interattiva e analisi dei dati sugli incidenti di soccorso alpino in provincia di Bolzano.
Progetto collegato al video del canale YouTube *The Walking Nose*.

**Dashboard:** apri `index.html` nel browser (è un file unico, funziona anche offline), oppure usa la versione online su GitHub Pages.

## Cosa c'è

| Cartella | Contenuto |
|---|---|
| `index.html` | La dashboard: vista per quota, incroci tra caratteristiche, mappa di concentrazione. |
| `dashboard/` | Come è costruita: template, preparazione dei dati, geometrie dei comuni. |
| `analisi/quote/` | Calcolo della quota di ogni evento dal modello digitale del terreno e validazione. |
| `analisi/vicinanza/` | Distanza degli eventi da rifugi, bivacchi, malghe e impianti (OpenStreetMap). |
| `analisi/trend/` | Analisi dei trend 2022–2025 sull'escursionismo (regressioni, intervalli di confidenza). |

## Fonti dei dati

- **Incidenti:** banca dati degli incidenti alpini, Agenzia provinciale per la Protezione civile (Provincia autonoma di Bolzano), con interventi del Soccorso Alpino AVS e del CNSAS. Dati letti dal sito il 11 ottobre 2026; il 2026 arriva al 4 ottobre, il 2020 contiene solo novembre e dicembre. Link: https://info-afbs.provinz.bz.it/AUDB/
- **Quota:** modello EU-DEM (celle da 25 m) tramite OpenTopoData. Non è un dato della banca dati: è calcolato dalle coordinate registrate.
- **Confini dei comuni:** ISTAT, licenza CC-BY, semplificati.
- **Rifugi, bivacchi, malghe, impianti:** © contributori OpenStreetMap, licenza ODbL.

## Limiti da tenere presenti

- Le coordinate sono quelle registrate dal soccorso: possono indicare il luogo del recupero o un punto di riferimento, non il punto esatto dell'incidente.
- **Validazione della quota** (campione di 400 eventi, vedi `analisi/quote/validazione_quote_report.txt`): rispetto a una seconda fonte indipendente (Copernicus 90 m) lo scarto mediano è di 10 m e nel 90% dei casi resta entro 40 m. Se la posizione fosse sbagliata di 100 m, la quota cambierebbe in genere di 22 m. Le fasce da 500 m sono robuste, quelle più strette meno.
- 57 eventi del 2026 (sci e snowboard) hanno tutti le stesse coordinate a Bolzano: sono un segnaposto. Compaiono nei conteggi e negli incroci, non nei grafici per quota né sulla mappa.
- La mappa mostra dove si registrano gli incidenti, non dove il rischio è più alto: dove passa più gente ce ne sono di più.
- Il 2021 non è confrontabile con gli altri anni ed è escluso dalle analisi sui trend.

## Riproducibilità

I dati grezzi della banca dati **non sono inclusi** in questa repo: vanno scaricati dal sito dell'Agenzia (https://info-afbs.provinz.bz.it/AUDB/), nel rispetto delle sue condizioni di riuso. Gli script in `analisi/` leggono file CSV con nomi indicati nelle intestazioni e non girano senza di essi. `dashboard/build_data3.py` contiene percorsi locali dell'ambiente in cui è stato eseguito: è qui per trasparenza sul metodo, non è un comando da lanciare così com'è.

## Licenza

Da definire dall'autore. Il codice non ha ancora una licenza; i dati restano soggetti alle condizioni delle fonti sopra.
