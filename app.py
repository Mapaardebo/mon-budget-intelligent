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

# Liste des mots à ignorer automatiquement
MOTS_INTERDITS = ["STATION", "RUE", "AVENUE", "BOULEVARD", "TEL:", "MERCI", "REVOIR", "TOTAL", "CB", "VISA", "TICKET", "SIRET", "DATE", "MAGASIN"]

# Dictionnaire complet avec tes 11 catégories
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
    "AUTRE": []
}

# --- 2. FONCTIONS UTILES ---
def charger_memoire():
    if os.path.exists(NOM_DICT):
        try:
            with open(NOM_DICT, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return DICT_INITIAL
    return DICT_INITIAL

def sauvegarder_memoire(dico):
    with open(NOM_DICT, 'w', encoding='utf-8') as f:
        json.dump(dico, f, indent=4, ensure_ascii=False)

# Initialisation de la session
if 'memoire' not in st.session_state:
    st.session_state.memoire = charger_memoire()

# --- 3. INTERFACE PAR ONGLETS ---
tab1, tab2 = st.tabs(["📸 Scanner un Ticket", "📊 Mes Statistiques"])

with tab1:
    st.header("Nouveau Scan")
    source_photo = st.radio("Source de l'image :", ("Appareil photo", "Télécharger un fichier"))
    
    if source_photo == "Appareil photo":
        image_file = st.camera_input("Prenez le ticket en photo")
    else:
        image_file = st.file_uploader("Choisissez une image...", type=['jpg', 'jpeg', 'png'])

    if image_file is not None:
        img = Image.open(image_file)
        st.image(img, caption="Ticket chargé", use_column_width=True)
        
        if st.button("Lancer l'analyse ✨"):
            with st.spinner("Lecture du ticket en cours..."):
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
                    if any(mot in phrase for mot in MOTS_INTERDITS):
                        continue

                    match = re.search(r'(\d+)[\s.,](\d{2})\b', phrase)
                    if match:
                        prix = float(f"{match.group(1)}.{match.group(2)}")
                        nom = phrase.replace(match.group(0), "").strip()
                        
                        if len(nom) > 3:
                            cat_trouvee = "INCONNU"
                            for cat, mots in st.session_state.memoire.items():
                                if any(m in nom for m in mots):
                                    cat_trouvee = cat; break
                            new_data.append({"Article": nom, "Prix": prix, "Cat": cat_trouvee})
                
                st.session_state.temp_items = new_data

    if 'temp_items' in st.session_state and len(st.session_state.temp_items) > 0:
        st.subheader("Validation des articles")
        st.info("Décochez 'Garder' pour les lignes inutiles (adresses, taxes, etc.)")
        
        df_items = pd.DataFrame(st.session_state.temp_items)
        df_items.insert(0, "Garder", True)
        
        edited_df = st.data_editor(df_items, use_container_width=True, num_rows="dynamic")
        
        if st.button("Enregistrer la sélection"):
            valid_items = edited_df[edited_df["Garder"] == True]
            
            if not valid_items.empty:
                final_list = []
                date_str = datetime.now().strftime("%d/%m/%Y")
                
                for _, row in valid_items.iterrows():
                    final_list.append([date_str, row['Article'], row['Prix'], row['Cat']])
                
                # Sauvegarde CSV
                df_save = pd.DataFrame(final_list, columns=['Date', 'Article', 'Prix', 'Categorie'])
                df_save.to_csv(NOM_CSV, mode='a', index=False, header=not os.path.exists(NOM_CSV), sep=';', encoding='utf-8-sig')
                
                # --- APPRENTISSAGE SÉCURISÉ ---
                for row in final_list:
                    cat_nom = row[3]
                    art_nom = row[1]
                    # On vérifie si la catégorie existe dans la mémoire actuelle
                    if cat_nom in st.session_state.memoire:
                        mots_de_l_article = art_nom.split()
                        if mots_de_l_article:
                            premier_mot = mots_de_l_article[0]
                            if len(premier_mot) > 3 and premier_mot not in st.session_state.memoire[cat_nom]:
                                st.session_state.memoire[cat_nom].append(premier_mot)
                
                sauvegarder_memoire(st.session_state.memoire)
                st.success(f"✅ {len(final_list)} articles enregistrés !")
            
            del st.session_state.temp_items
            st.rerun()

with tab2:
    st.header("Analyse de vos dépenses")
    if os.path.exists(NOM_CSV) and os.path.getsize(NOM_CSV) > 0:
        try:
            df = pd.read_csv(NOM_CSV, sep=';', encoding='utf-8-sig')
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
            df['Prix'] = pd.to_numeric(df['Prix'], errors='coerce')
            df = df.dropna(subset=['Date', 'Prix'])
            
            if not df.empty:
                st.subheader("Répartition par catégorie")
                recap = df.groupby('Categorie')['Prix'].sum().sort_values(ascending=False)
                st.bar_chart(recap)
                
                st.subheader("Historique des achats")
                st.dataframe(df.sort_values('Date', ascending=False), use_container_width=True)
                
                if st.button("Effacer tout l'historique"):
                    os.remove(NOM_CSV)
                    st.rerun()
            else:
                st.info("Aucune donnée valide à afficher.")
        except Exception as e:
            st.error(f"Erreur de lecture du fichier budget. Essayez de le réinitialiser.")
    else:
        st.info("Scannez un ticket pour commencer !")
