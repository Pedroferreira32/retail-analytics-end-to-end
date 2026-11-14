# Retail Analytics — Proyecto de datos End-to-End

[English](README.md) · [Português](README.pt-BR.md) · [Italiano](README.it.md)

Desarrollé este proyecto para conectar preguntas comerciales con calidad de datos, modelado dimensional e inteligencia de negocios. Utilicé el **Brazilian E-Commerce Public Dataset by Olist**, con operaciones reales anonimizadas de 2016–2018.

Un pedido puede tener varios artículos, pagos y reseñas. Traté cada relación de forma explícita para evitar la multiplicación de importes y reconcilié los resultados mediante Python y SQL.

## Resultados verificados

| Indicador | Resultado |
| --- | ---: |
| Pedidos realizados, todos los estados | 99.441 |
| Pedidos entregados | 96.478 |
| GMV de mercancía entregada, sin envío | R$ 13.221.498,11 |
| Importe medio por pedido entregado, sin envío | R$ 137,04 |
| Tasa de retraso entre entregas observadas | 6,77% |
| Última valoración media de pedidos entregados con reseña | 4,16 / 5 |

El GMV no representa los ingresos o el beneficio de Olist. Los meses en los extremos de la base están incompletos o tienen pocas observaciones; no permiten afirmar que el negocio se desplomó.

## Componentes

- ETL Python/pandas con contratos de datos, calidad y trazabilidad SHA-256.
- Cuatro dimensiones y tres tablas de hechos, con importes en céntimos enteros.
- SQL reproducible localmente en DuckDB y publicable en BigQuery.
- Cargador BigQuery con snapshots, particiones, clustering y conciliación.
- Proyecto Power BI PBIP/PBIR con cuatro páginas, 20 medidas DAX y parámetros CSV/BigQuery.
- Pruebas automatizadas, cobertura mínima del 80%, GitHub Actions en Linux/Windows y documentación técnica.

## Ejecutar

Python 3.11/3.12, con el entorno virtual activado:

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
retail download --raw-dir data/raw
retail run --raw-dir data/raw --output-dir data/processed --source-kind olist
python scripts/prepare_powerbi.py
pytest --cov=retail_analytics --cov-report=term-missing
```

El ETL completo y las conciliaciones se ejecutaron con datos reales. Los archivos de Power BI pasaron las comprobaciones de esquemas Microsoft y referencias al modelo; todavía falta validar la actualización en Desktop y exportar un PBIX real en Windows. El cargador BigQuery está implementado y probado con un cliente simulado; la carga real requiere un proyecto GCP autorizado. La publicación en Power BI Service requiere una cuenta y un espacio de trabajo conectados.

[Documentación completa](README.md) · [Métricas](docs/metrics.md) · [Evidencias](docs/evidence/README.md) · [Power BI](powerbi/README.md) · [BigQuery](docs/bigquery.md)

Datos: **Olist**, [Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), **CC BY-NC-SA 4.0**, uso educativo no comercial. Código original: MIT. Autor: **Pedro Aurélio Gonçalves Ferreira**.
