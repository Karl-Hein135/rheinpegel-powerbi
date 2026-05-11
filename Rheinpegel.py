import requests
import pandas as pd
from io import StringIO
from datetime import datetime

pegel_liste = [
    {"name": "DUISBURG-RUHRORT", "url_name": "DUISBURG-RUHRORT"},
    {"name": "KÖLN", "url_name": "K%C3%96LN"},
    {"name": "KOBLENZ", "url_name": "KOBLENZ"},
    {"name": "KAUB", "url_name": "KAUB"},
    {"name": "OESTRICH", "url_name": "OESTRICH"},
]

aktuelle_werte = []
vorhersage_werte = []


def sauber(wert):
    if pd.isna(wert):
        return ""
    return str(wert).strip()


def ist_gueltiger_wert(wert):
    wert = sauber(wert)
    return wert not in ["", "--", "nan", "NaN"]


def label_fuer_spalte(original_label, vorkommen):
    if vorkommen == 1:
        return original_label
    if vorkommen == 2:
        return f"{original_label} Abweichung"
    if vorkommen == 3:
        return f"{original_label} Vorhersage"
    return f"{original_label} {vorkommen}"


for pegel in pegel_liste:
    name = pegel["name"]
    url_name = pegel["url_name"]

    url = f"https://www.elwis.de/DE/dynamisch/Wasserstaende/Pegelvorhersage:{url_name}"

    print(f"Lade {name} ...")

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        tables = pd.read_html(StringIO(response.text))
        df = tables[0]

        # Nur echte Datenzeilen mit Uhrzeit verwenden
        daten = df[df[1].astype(str).str.contains(":")].copy()

        # Kopfzeile mit Datum/Tag-Angaben
        kopfzeile = df.iloc[2]

        # Spalten-Mapping bauen:
        # gleiche ELWIS-Labels können mehrfach vorkommen:
        # z.B. Heute, Heute Abweichung, Heute Vorhersage
        spalten_infos = []
        basis_sortierung = {}
        vorkommen_je_label = {}
        basis_counter = 1

        for spalte in range(2, len(df.columns)):
            original_label = sauber(kopfzeile[spalte])

            if original_label == "":
                continue

            if original_label.lower().startswith("spalte"):
                continue

            if original_label not in basis_sortierung:
                basis_sortierung[original_label] = basis_counter
                basis_counter += 1

            vorkommen_je_label[original_label] = vorkommen_je_label.get(original_label, 0) + 1
            vorkommen = vorkommen_je_label[original_label]

            tag_label = label_fuer_spalte(original_label, vorkommen)

            # Sortierung:
            # 10, 11, 12 je Tagesblock
            # damit Wert, Abweichung, Vorhersage direkt nebeneinander bleiben
            sortierung = basis_sortierung[original_label] * 10 + vorkommen

            spalten_infos.append({
                "spalte": spalte,
                "tag_label": tag_label,
                "sortierung": sortierung
            })

        # Vorhersagewerte im stabilen Langformat speichern
        for _, row in daten.iterrows():
            uhrzeit = sauber(row[1])

            for info in spalten_infos:
                spalte = info["spalte"]
                wert = sauber(row[spalte])

                if wert == "":
                    continue

                vorhersage_werte.append({
                    "Pegel": name,
                    "Uhrzeit": uhrzeit,
                    "Tag_Label": info["tag_label"],
                    "Sortierung": info["sortierung"],
                    "Wert": wert,
                    "Aktualisiert_am": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        # Aktueller Wert für Dashboard:
        # Wir nehmen den neuesten gültigen Wert aus den heutigen Wert-Spalten.
        letzte_werte = []

        for _, row in daten.iterrows():
            uhrzeit = sauber(row[1])

            # meistens: Spalte 4 = heutiger Messwert, Spalte 5 = Abweichung
            wert = sauber(row[4]) if 4 in df.columns else ""
            abweichung = sauber(row[5]) if 5 in df.columns else ""

            if ist_gueltiger_wert(wert):
                letzte_werte.append({
                    "Pegel": name,
                    "Uhrzeit": uhrzeit,
                    "Wert_cm": wert,
                    "Abweichung": abweichung,
                    "Aktualisiert_am": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

        if letzte_werte:
            aktuelle_werte.append(letzte_werte[-1])
            print(
                f"  Aktuell: {letzte_werte[-1]['Wert_cm']} cm "
                f"um {letzte_werte[-1]['Uhrzeit']}"
            )

    except Exception as e:
        print(f"Fehler bei {name}: {e}")


# CSV 1: aktuelle Pegelwerte
df_aktuell = pd.DataFrame(aktuelle_werte)

df_aktuell.to_csv(
    "rheinpegel_aktuell.csv",
    index=False,
    encoding="utf-8-sig"
)


# CSV 2: stabile Vorhersagewerte für Power BI
df_vorhersage = pd.DataFrame(vorhersage_werte)

df_vorhersage = df_vorhersage[
    [
        "Pegel",
        "Uhrzeit",
        "Tag_Label",
        "Sortierung",
        "Wert",
        "Aktualisiert_am"
    ]
]

df_vorhersage.to_csv(
    "rheinpegel_vorhersage.csv",
    index=False,
    encoding="utf-8-sig"
)


print("\nFertig.")
print("CSV gespeichert:")
print("- rheinpegel_aktuell.csv")
print("- rheinpegel_vorhersage.csv")