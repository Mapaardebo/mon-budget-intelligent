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

# Dictionnaire par défaut
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
        with open(NOM_DICT, 'r', encoding='utf-8') as f: return json.load(f)
    return DICT_INITIAL

def sauvegarder_memoire(dico):
    with open(NOM_DICT, 'w', encoding='utf-8') as f:
        json.dump(dico, f, indent=4, ensure_ascii=False)

# Initialisation de la session pour garder les données en mémoire
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
                # Conversion image pour EasyOCR
                img_np = np.array(img)
                reader = easyocr.Reader(['fr'])
                results = reader.readtext(img_np)
                
                # Regroupement des lignes
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
                
                # Traitement des données
                new_data = []
                for y in sorted(lignes.keys()):
                    phrase = " ".join(lignes[y]).upper()
                    match = re.search(r'(\d+)[\s.,](\d{2})\b', phrase)
                    if match:
                        prix = float(f"{match.group(1)}.{match.group(2)}")
                        nom = phrase.replace(match.group(0), "").strip()
                        if len(nom) > 3:
                            # Tentative de classification auto
                            cat_trouvee = "INCONNU"
                            for cat, mots in st.session_state.memoire.items():
                                if any(m in nom for m in mots):
                                    cat_trouvee = cat; break
                            new_data.append({"Article": nom, "Prix": prix, "Cat": cat_trouvee})
                
                st.session_state.temp_items = new_data

    # Si des articles ont été détectés, on demande validation
    if 'temp_items' in st.session_state:
        st.subheader("Validation des articles")
        final_list = []
        with st.form("form_validation"):
            for i, item in enumerate(st.session_state.temp_items):
                col1, col2, col3 = st.columns([3, 1, 2])
                with col1:
                    nom_art = st.text_input("Article", item['Article'], key=f"n_{i}")
                with col2:
                    prix_art = st.number_input("Prix", value=item['Prix'], key=f"p_{i}")
                with col3:
                    options = list(st.session_state.memoire.keys())
                    index_defaut = options.index(item['Cat']) if item['Cat'] in options else len(options)-1
                    cat_art = st.selectbox("Catégorie", options, index=index_defaut, key=f"c_{i}")
                final_list.append([datetime.now().strftime("%d/%m/%Y"), nom_art, prix_art, cat_art])
            
            if st.form_submit_button("Enregistrer dans le Budget"):
                # Sauvegarde CSV
                df_new = pd.DataFrame(final_list, columns=['Date', 'Article', 'Prix', 'Categorie'])
                df_new.to_csv(NOM_CSV, mode='a', index=False, header=not os.path.exists(NOM_CSV), sep=';', encoding='utf-8-sig')
                
                # Apprentissage auto (mise à jour du dico)
                for row in final_list:
                    mot = row[1].split()[0]
                    if len(mot) > 3 and mot not in st.session_state.memoire[row[3]]:
                        st.session_state.memoire[row[3]].append(mot)
                sauvegarder_memoire(st.session_state.memoire)
                
                st.success("✅ Ticket enregistré !")
                del st.session_state.temp_items

with tab2:
    st.header("Analyse de vos dépenses")
    if os.path.exists(NOM_CSV):
        df = pd.read_csv(NOM_CSV, sep=';', encoding='utf-8-sig')
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True)
        
        # Résumé par catégorie
        st.subheader("Répartition par catégorie")
        recap = df.groupby('Categorie')['Prix'].sum().sort_values(ascending=False)
        st.bar_chart(recap)
        
        # Tableau complet
        st.subheader("Historique des achats")
        st.dataframe(df.sort_values('Date', ascending=False))
        
        # Bouton pour effacer (optionnel)
        if st.button("Effacer tout l'historique"):
            os.remove(NOM_CSV)
            st.rerun()
    else:
        st.info("Aucune donnée enregistrée pour le moment. Allez dans l'onglet Scanner !")
