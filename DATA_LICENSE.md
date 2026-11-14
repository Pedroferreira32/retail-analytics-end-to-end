# Olist data attribution and license

**Original creator:** Olist and the collaborators credited on the dataset page.

**Dataset:** Brazilian E-Commerce Public Dataset by Olist.

**Original source:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

**Dataset license:** Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International.

**License text:** https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode

The original dataset is real, anonymized Brazilian marketplace data covering 2016–2018. This independent project uses it for noncommercial education and a professional learning portfolio. It does not claim ownership of the data or imply endorsement by Olist.

Raw Olist CSVs are excluded from Git. The downloader retrieves them from the original Kaggle publisher. Source SHA-256 fingerprints and row counts are recorded in each validated run.

Changes made for this project include whitespace and type normalization, currency conversion to integer cents, ZIP-prefix aggregation for geolocation, deterministic review selection, dimensional modeling and aggregation. Exported analytical tables omit review free text. Derived Olist analytical results, CSV aggregates, documentation containing those results and figures are shared under **CC BY-NC-SA 4.0**, with this attribution.

The project's original software is separately licensed under MIT. The MIT license does not replace the Olist data license. Small test fixtures are authored synthetic examples and contain no copied Olist transactions.
