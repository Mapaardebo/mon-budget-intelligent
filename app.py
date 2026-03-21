import streamlit as st
import easyocr
import pandas as pd
import re
import os
import json
import matplotlib.pyplot as plt
from datetime import datetime
from PIL import Image
import numpy as np

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Mon Budget Intelligent", layout="centered")
st.title("🛒 Mon Assistant Budget")

NOM_DICT = 'mon_dictionnaire.json'
NOM_CSV = 'mon_budget.csv'

# Mots à ignorer (Infos magasin)
MOTS_INTERDITS = ["STATION", "RUE", "AVENUE", "BOULEVARD", "TEL:", "MERCI", "REVOIR", "TOTAL", "CB", "VISA", "TICKET", "SIRET", "DATE", "MAGASIN"]

# Mots indiquant une réduction
MOTS_REDUCTIONS = ["REMISE", "REDUC", "PROMO", "ESCOMPTE", "RABAIS", "BON ", "AVOIR", "DEDUCTION", "NUTRI-BOOST", "NUTRI BOOST"]

# Dictionnaire complet avec la nouvelle catégorie REMISES
DICT_INITIAL = {
    "FRUITS": ["POMME", "BANANE", "ORANGE", "PINK", "LADY"],
    "LÉGUMES": ["CAROTTE", "TOMATE", "COURGETTE", "SALADE", "CRISE"],
    "VIANDE": ["POULET", "BOEUF", "STEAK", "JAMBON"],
    "POISSON": ["SAUMON", "CABILLAUD", "THON"],
    "PRODUITS LAITIERS": ["LAIT", "YAOURT", "BEURRE", "FROMAGE", "GRANA"],
    "ÉPICERIE": ["PATES", "RIZ", "FARINE", "HUILE", "OEUF"],
    "SUCRERIES": ["CHOCOLAT", "BISCUIT", "CHOC", "COOKIE"],
    "BOISSONS": ["EAU", "JUS", "SODA", "COLA"],
    "BOISSONS ALCOOLISÉES": ["VIN", "BIERE"],
    "HYGIÈNE CORPORELLE": ["SAVON", "DENTIFRICE", "SHAMPOOING"],
    "ENTRETIEN DE LA MAISON": ["LESSIVE", "PAIC", "SOPALIN"],
    "REMISES": ["REMISE", "REDUC", "PROMO", "NUTRI-BOOST", "AVOIR"], # Nouvelle catégorie
    "AUTRE": []
}

# --- 2. FONCTIONS UTILES ---
def charger_memoire():
    if os.path.exists(NOM_DICT):
        try:
            with open(NOM_DICT, 'r', encoding='utf-8') as f: return json.load(f)
        except: return DICT_INITIAL
    return DICT_INITIAL

def sauvegarder_memoire(dico):
    with open(NOM_DICT, 'w', encoding='utf-8') as f:
        json.dump(dico, f, indent=4, ensure_ascii=False)

if 'memoire' not in st.session_state:
    st.session_state.memoire = charger_memoire()

# --- 3. INTERFACE ---
tab1, tab2 = st.tabs(["📸 Scanner un Ticket", "📊 Mes Statistiques"])

with tab1:
    st.header("Nouveau Scan")
    source_photo = st.radio("Source :", ("Appareil photo", "Télécharger un fichier"))
    
    if source_photo == "Appareil photo":
        image_file = st.camera_input("Prenez le ticket")
    else:
        image_file = st.file_uploader("Image...", type=['jpg', 'jpeg', 'png'])

    if image_file is not None:
        img = Image.open(image_file)
        st.image(img, use_column_width=True)
        
        if st.button("Lancer l'analyse ✨"):
            with st.spinner("Analyse..."):
                img_np = np.array(img)
                reader = easyocr.Reader(['fr'])
                results = reader.readtext(img_np)
                
                lignes = {}
                for (bbox, text, prob) in results:
                    if prob > 0.20:
                        y = bbox[0][1]
                        trouve = False
                        for y_l in lignes.keys():
                            if abs(y - y_l) < 15:
                                lignes[y_l].append(text)
                                trouve = True; break
                        if not trouve: lignes[y] = [text]
                
                new_data = []
                for y in sorted(lignes.keys()):
                    phrase = " ".join(lignes[y]).upper()
                    if any(mot in phrase for mot in MOTS_INTERDITS): continue

                    match = re.search(r'(-?\d+)[\s.,](\d{2})(-?)\b', phrase)
                    if match:
                        valeur = f"{match.group(1)}.{match.group(2)}"
                        prix = float(valeur)
                        
                        # Détection réduction
                        est_reduction = (match.group(3) == "-" or "-" in match.group(1) or any(r in phrase for r in MOTS_REDUCTIONS))
                        
                        if est_reduction and prix > 0: prix = -prix
                        
                        nom = phrase.replace(match.group(0), "").strip()
                        if len(nom) > 3:
                            # Priorité à la catégorie REMISES si c'est une réduction
                            cat_trouvee = "REMISES" if est_reduction else "INCONNU"
                            
                            if cat_trouvee == "INCONNU":
                                for cat, mots in st.session_state.memoire.items():
                                    if any(m in nom for m in mots):
                                        cat_trouvee = cat; break
                            
                            new_data.append({"Article": nom, "Prix": prix, "Cat": cat_trouvee})
                
                st.session_state.temp_items = new_data

    if 'temp_items' in st.session_state and len(st.session_state.temp_items) > 0:
        st.subheader("Validation")
        df_items = pd.DataFrame(st.session_state.temp_items)
        df_items.insert(0, "Garder", True)
        edited_df = st.data_editor(df_items, use_container_width=True, num_rows="dynamic")
        
        if st.button("Enregistrer"):
            valid_items = edited_df[edited_df["Garder"] == True]
            if not valid_items.empty:
                final_list = []
                date_str = datetime.now().strftime("%d/%m/%Y")
                for _, row in valid_items.iterrows():
                    final_list.append([date_str, row['Article'], row['Prix'], row['Cat']])
                
                df_save = pd.DataFrame(final_list, columns=['Date', 'Article', 'Prix', 'Categorie'])
                df_save.to_csv(NOM_CSV, mode='a', index=False, header=not os.path.exists(NOM_CSV), sep=';', encoding='utf-8-sig')
                
                # Apprentissage sécurisé
                for row in final_list:
                    cat_nom, art_nom = row[3], row[1]
                    if cat_nom in st.session_state.memoire:
                        mots = art_nom.split()
                        if mots and len(mots[0]) > 3:
                            if mots[0] not in st.session_state.memoire[cat_nom]:
                                st.session_state.memoire[cat_nom].append(mots[0])
                
                sauvegarder_memoire(st.session_state.memoire)
                st.success("✅ Enregistré !")
            del st.session_state.temp_items
            st.rerun()

with tab2:
    st.header("Analyse")
    if os.path.exists(NOM_CSV) and os.path.getsize(NOM_CSV) > 0:
        df = pd.read_csv(NOM_CSV, sep=';', encoding='utf-8-sig')
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        df['Prix'] = pd.to_numeric(df['Prix'], errors='coerce')
        df = df.dropna(subset=['Date', 'Prix'])
        
        if not df.empty:
            st.metric("Total Dépensé (net)", f"{round(df['Prix'].sum(), 2)} €")
            
            st.subheader("Impact par catégorie")
            recap = df.groupby('Categorie')['Prix'].sum().sort_values(ascending=False)
            st.bar_chart(recap)
            
            st.subheader("Historique")
            st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)
            
            if st.button("Effacer l'historique"):
                os.remove(NOM_CSV)
                st.rerun()
