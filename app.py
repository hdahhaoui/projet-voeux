import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- Configuration générale ---
st.set_page_config(
    page_title="Choix des matières - Département Génie Civil",
    page_icon="🏗️",
    layout="wide"
)

DATA_DIR = "data"
MATIERES_FILE = os.path.join(DATA_DIR, "matieres_all.csv")
SOUMISSIONS_FILE = os.path.join(DATA_DIR, "soumissions.csv")

os.makedirs(DATA_DIR, exist_ok=True)

# --- Charger la base des matières ---
@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        df = pd.read_csv(MATIERES_FILE)
        return df.fillna("")
    else:
        st.warning("⚠️ Fichier des matières introuvable. Veuillez ajouter 'matieres_all.csv' dans le dossier data/.")
        return pd.DataFrame(columns=["course_code", "course_title", "level_code", "track_code", "ec_type"])

matieres_df = load_matieres()

# --- Titre principal ---
st.title("🎓 Plateforme de choix des matières")
st.markdown("**Département de Génie Civil - Université de Tlemcen**")
st.markdown("---")

# --- Informations de l'enseignant ---
st.header("👩‍🏫 Informations personnelles")

col1, col2 = st.columns(2)
with col1:
    nom = st.text_input("Nom de l'enseignant(e)")
with col2:
    prenom = st.text_input("Prénom de l'enseignant(e)")

email = st.text_input("Adresse e-mail universitaire (facultatif)")

st.markdown("---")

# --- Filtrage des matières ---
if not matieres_df.empty:
    niveaux = sorted(matieres_df["level_code"].dropna().unique().tolist())
    niveau_choisi = st.selectbox("📘 Sélectionnez le niveau :", [""] + niveaux)

    if niveau_choisi:
        parcours = sorted(matieres_df.query("level_code == @niveau_choisi")["track_code"].dropna().unique().tolist())
        parcours_choisi = st.selectbox("🎯 Parcours :", [""] + parcours)

        if parcours_choisi:
            subset = matieres_df.query("level_code == @niveau_choisi and track_code == @parcours_choisi")
            st.subheader(f"Matières disponibles ({len(subset)})")

            if len(subset) > 0:
                choix = st.multiselect(
                    "Sélectionnez vos matières (au moins 8 matières au total sur tous niveaux confondus) :",
                    options=subset["course_title"].tolist()
                )

                # Ajout d'un classement par priorité
                priorites = {}
                for c in choix:
                    priorites[c] = st.number_input(f"Priorité pour **{c}**", 1, 10, step=1)

                remarque = st.text_area("📝 Recommandations / Remarques / Préférences d'emploi du temps")

                # Bouton d'enregistrement
                if st.button("💾 Enregistrer mes choix"):
                    if nom.strip() == "" or prenom.strip() == "":
                        st.error("Veuillez renseigner votre nom et prénom.")
                    elif len(choix) < 8:
                        st.error("Vous devez sélectionner **au moins 8 matières**.")
                    else:
                        # Enregistrer dans le CSV
                        date_ = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        records = []
                        for mat in choix:
                            record = {
                                "nom": nom,
                                "prenom": prenom,
                                "email": email,
                                "niveau": niveau_choisi,
                                "parcours": parcours_choisi,
                                "matiere": mat,
                                "priorite": priorites.get(mat, ""),
                                "remarques": remarque,
                                "date_soumission": date_
                            }
                            records.append(record)

                        df_new = pd.DataFrame(records)
                        if os.path.exists(SOUMISSIONS_FILE):
                            df_old = pd.read_csv(SOUMISSIONS_FILE)
                            df_final = pd.concat([df_old, df_new], ignore_index=True)
                        else:
                            df_final = df_new
                        df_final.to_csv(SOUMISSIONS_FILE, index=False)

                        st.success("✅ Vos choix ont bien été enregistrés !")
                        st.download_button(
                            "📥 Télécharger mon récapitulatif",
                            data=df_new.to_csv(index=False).encode("utf-8"),
                            file_name=f"choix_{nom}_{prenom}.csv",
                            mime="text/csv"
                        )

# --- Pied de page ---
st.markdown("---")
st.caption("🧱 Application développée par le Département de Génie Civil - Université de Tlemcen © 2025")
