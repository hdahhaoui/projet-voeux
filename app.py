import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# =======================
# CONFIG GÉNÉRALE
# =======================
st.set_page_config(
    page_title="Choix des matières - Département Génie Civil",
    page_icon="🏗️",
    layout="wide",
)

DATA_DIR = os.getenv("DATA_PATH", "data")
MATIERES_FILE = os.path.join(DATA_DIR, "matieres_all.csv")
SOUMISSIONS_FILE = os.path.join(DATA_DIR, "soumissions.csv")
ADMIN_PASS = os.getenv("ADMIN_PASS", "")  # définis sur Render si tu veux protéger l’admin

os.makedirs(DATA_DIR, exist_ok=True)

# =======================
# UTILS
# =======================
@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        df = pd.read_csv(MATIERES_FILE).fillna("")
    else:
        df = pd.DataFrame(columns=["course_code","course_title","level_code","track_code","ec_type"])
    return df

@st.cache_data
def load_soumissions():
    if os.path.exists(SOUMISSIONS_FILE):
        return pd.read_csv(SOUMISSIONS_FILE).fillna("")
    # squelette si vide
    cols = ["nom","prenom","email","niveau","parcours","matiere","priorite","remarques","date_soumission"]
    return pd.DataFrame(columns=cols)

def save_soumissions(df_new: pd.DataFrame):
    if os.path.exists(SOUMISSIONS_FILE):
        old = pd.read_csv(SOUMISSIONS_FILE)
        final = pd.concat([old, df_new], ignore_index=True)
    else:
        final = df_new
    final.to_csv(SOUMISSIONS_FILE, index=False)

def to_excel_bytes(**sheets):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=name[:31] or "Sheet1")
    bio.seek(0)
    return bio

# =======================
# SIDEBAR
# =======================
matieres_df = load_matieres()
st.sidebar.header("Navigation")
mode = st.sidebar.radio("Mode", ["Enseignant", "Admin"])

# =======================
# MODE ENSEIGNANT
# =======================
if mode == "Enseignant":
    st.title("🎓 Plateforme de choix des matières")
    st.caption("Département de Génie Civil")

    st.header("👩‍🏫 Informations personnelles")
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Nom")
    with c2:
        prenom = st.text_input("Prénom")
    email = st.text_input("Adresse e-mail universitaire (facultatif)")

    st.divider()

    if matieres_df.empty:
        st.warning("⚠️ `data/matieres_all.csv` est introuvable ou vide.")
        st.stop()

    niveaux = sorted(matieres_df["level_code"].dropna().unique().tolist())
    niveau_choisi = st.selectbox("📘 Niveau", [""] + niveaux)

    choix, priorites = [], {}
    remarque = ""

    if niveau_choisi:
        parcours = sorted(matieres_df.query("level_code == @niveau_choisi")["track_code"].dropna().unique().tolist())
        parcours_choisi = st.selectbox("🎯 Parcours", [""] + parcours)

        if parcours_choisi:
            sub = matieres_df.query("level_code == @niveau_choisi and track_code == @parcours_choisi")
            st.subheader(f"Matières disponibles ({len(sub)})")
            if len(sub) > 0:
                choix = st.multiselect("Sélectionnez vos matières (≥ 8 au total sur tous niveaux confondus) :",
                                       options=sub["course_title"].tolist())
                for c in choix:
                    priorites[c] = st.number_input(f"Priorité pour **{c}**", min_value=1, step=1, key=f"prio_{c}")

                remarque = st.text_area("📝 Recommandations / Remarques / Préférences EDT")

    if st.button("💾 Enregistrer mes choix", type="primary"):
        if not nom.strip() or not prenom.strip():
            st.error("Veuillez renseigner votre nom et prénom.")
        elif len(choix) < 8:
            st.error("Vous devez sélectionner **au moins 8 matières**.")
        elif len(priorites) != len(set(priorites.values())):
            st.error("Les **priorités doivent être uniques** (1,2,3,…).")
        else:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_rows = []
            for mat in choix:
                new_rows.append({
                    "nom": nom,
                    "prenom": prenom,
                    "email": email,
                    "niveau": niveau_choisi,
                    "parcours": parcours_choisi,
                    "matiere": mat,
                    "priorite": priorites.get(mat, ""),
                    "remarques": remarque,
                    "date_soumission": now,
                })
            df_new = pd.DataFrame(new_rows)
            save_soumissions(df_new)

            st.success("✅ Vos choix ont été enregistrés.")
            st.download_button(
                "📥 Télécharger mon récapitulatif (CSV)",
                df_new.to_csv(index=False).encode("utf-8"),
                file_name=f"choix_{nom}_{prenom}.csv",
                mime="text/csv",
            )

# =======================
# MODE ADMIN
# =======================
else:
    st.title("🛠️ Administration – Vœux enseignants")

    # Protection simple par code
    if ADMIN_PASS:
        code = st.text_input("Code admin", type="password")
        if code != ADMIN_PASS:
            st.info("Entrez le code admin pour accéder aux données.")
            st.stop()

    df = load_soumissions()

    if df.empty:
        st.warning("Aucune soumission pour l'instant.")
        st.stop()

    # Filtres
    f1, f2, f3 = st.columns(3)
    with f1:
        sel_niv = st.multiselect("Niveaux", sorted(df["niveau"].dropna().unique().tolist()))
    with f2:
        sel_par = st.multiselect("Parcours", sorted(df["parcours"].dropna().unique().tolist()))
    with f3:
        sel_prof = st.multiselect("Enseignants", sorted((df["nom"] + " " + df["prenom"]).unique().tolist()))

    filtered = df.copy()
    if sel_niv: filtered = filtered[filtered["niveau"].isin(sel_niv)]
    if sel_par: filtered = filtered[filtered["parcours"].isin(sel_par)]
    if sel_prof and "nom" in df.columns and "prenom" in df.columns:
        full = (filtered["nom"] + " " + filtered["prenom"]).isin(sel_prof)
        filtered = filtered[full]

    st.subheader(f"📋 Soumissions ({len(filtered)})")
    st.dataframe(filtered.sort_values(["date_soumission","priorite"], ascending=[False, True]),
                 use_container_width=True, hide_index=True)

    # Agrégats
    st.subheader("📊 Synthèses")
    cA, cB, cC = st.columns(3)
    with cA:
        agg_niv = filtered.groupby("niveau").size().reset_index(name="nb_lignes")
        st.caption("Par niveau")
        st.dataframe(agg_niv, use_container_width=True, hide_index=True)
    with cB:
        agg_mat = filtered.groupby("matiere").size().reset_index(name="nb_voeux").sort_values("nb_voeux", ascending=False)
        st.caption("Top matières")
        st.dataframe(agg_mat, use_container_width=True, hide_index=True)
    with cC:
        if {"nom","prenom"}.issubset(filtered.columns):
            agg_prof = filtered.assign(enseignant=filtered["nom"]+" "+filtered["prenom"])\
                               .groupby("enseignant").size().reset_index(name="nb_lignes")\
                               .sort_values("nb_lignes", ascending=False)
            st.caption("Par enseignant")
            st.dataframe(agg_prof, use_container_width=True, hide_index=True)

    # Export Excel multi-feuilles
    st.subheader("📤 Export")
    xls = to_excel_bytes(
        Soumissions=filtered.sort_values(["date_soumission","priorite"], ascending=[False, True]),
        Par_niveau=agg_niv,
        Top_matieres=agg_mat,
    )
    st.download_button("⬇️ Export Excel (toutes vues)", xls.getvalue(), file_name="voeux_admin_export.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.caption("Astuce : définis la variable d’environnement **ADMIN_PASS** sur Render pour protéger l’accès.")
