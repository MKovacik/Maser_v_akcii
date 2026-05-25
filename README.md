# Masér v akcii — Harmonogram súťaže

Generátor harmonogramu pre súťaž "Masér v akcii". Aplikácia automaticky rozvrháva tímy na jednotlivé aktivity (masáže, šport, test, sprievodný program, obed) s využitím constraint programming solvera (Google OR-Tools CP-SAT).

## Odkazy

- **Aplikácia (Streamlit Cloud):** https://maservakcii.streamlit.app
- **Publikovaný harmonogram (GitHub Pages):** https://mkovacik.github.io/Maser_v_akcii/
- **Repozitár:** https://github.com/MKovacik/Maser_v_akcii

## Funkcie

- Automatické rozvrhovanie 11 tímov s minimalizáciou celkového času a maximalizáciou sprievodného programu
- Konfigurovateľné aktivity, časy, počty skupín
- Export do Excel a JSON
- Vizualizácia formou časovej osi, prehľadovej tabuľky a detailného pohľadu po tímoch
- Publikovanie na GitHub Pages (len pri lokálnom spustení)

## Spustenie lokálne

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Technológie

- Python, Streamlit
- Google OR-Tools (CP-SAT solver)
- Pandas, openpyxl
