# Retail Analytics — Progetto dati End-to-End

[English](README.md) · [Português](README.pt-BR.md) · [Español](README.es.md)

Ho realizzato questo progetto per collegare domande commerciali, qualità dei dati, modellazione dimensionale e business intelligence. Ho utilizzato il **Brazilian E-Commerce Public Dataset by Olist**, un insieme di dati reali anonimizzati relativi al periodo 2016–2018.

Un ordine può contenere più articoli, pagamenti e recensioni. Ho gestito queste relazioni separatamente per evitare la moltiplicazione degli importi e ho riconciliato i risultati attraverso Python e SQL.

## Risultati verificati

| Indicatore | Risultato |
| --- | ---: |
| Ordini complessivi | 99.441 |
| Ordini consegnati | 96.478 |
| GMV della merce consegnata, spedizione esclusa | R$ 13.221.498,11 |
| Valore medio per ordine consegnato, spedizione esclusa | R$ 137,04 |
| Tasso di ritardo sulle consegne osservate | 6,77% |
| Valutazione media più recente degli ordini consegnati con recensione | 4,16 / 5 |

Il GMV non rappresenta il fatturato o l'utile di Olist. I mesi ai margini del dataset sono incompleti o poco rappresentati e non dimostrano un reale crollo dell'attività.

## Componenti

- ETL Python/pandas con contratti, controlli di qualità e impronte SHA-256.
- Quattro dimensioni e tre tabelle dei fatti; importi in centesimi interi.
- SQL eseguibile localmente in DuckDB e pubblicabile in BigQuery.
- Caricamento BigQuery con snapshot, partizionamento, clustering e riconciliazione.
- Power BI PBIP/PBIR: quattro pagine, 20 misure DAX e parametri CSV/BigQuery.
- Test automatici, copertura minima dell'80%, GitHub Actions Linux/Windows e documentazione tecnica.

## Avvio

Python 3.11/3.12, con ambiente virtuale attivo:

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
python scripts/prepare_powerbi.py
pytest --cov=retail_analytics --cov-report=term-missing
```

L'ETL completo e le riconciliazioni sono stati eseguiti sui dati reali. La pubblicazione effettiva in BigQuery è riuscita nel progetto `retail-analytics-514717` tramite Cloud Shell: [schermata del risultato e undici conteggi riconciliati](docs/evidence/bigquery-cli-receipt.json). La configurazione IAM/WIF e la pubblicazione da GitHub Actions restano da completare. I file Power BI sono stati controllati tramite schemi Microsoft e riferimenti al modello; l'aggiornamento in Desktop e l'esportazione PBIX devono ancora essere verificati su Windows. La pubblicazione Power BI Service richiede un account e un workspace collegati.

[Documentazione completa](README.md) · [Metriche](docs/metrics.md) · [Risultati e prove](docs/evidence/README.md) · [Power BI](powerbi/README.md) · [BigQuery](docs/bigquery.md)

Dati: **Olist**, [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), **CC BY-NC-SA 4.0**, uso didattico non commerciale. Codice originale: MIT. Autore: **Pedro Aurélio Gonçalves Ferreira**.
