# app.py — Plateforme de vœux enseignants (Département GC)
# --------------------------------------------------------
# Dépendances : streamlit, pandas, xlsxwriter (inclus côté Streamlit Cloud)
# requirements.txt :
#   streamlit
#   pandas
#   python-dotenv
# --------------------------------------------------------

import os
from io import BytesIO
from datetime import datetime

import pandas as pd
import streamlit as st

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
ADMIN_PASS = os.getenv("ADMIN_PASS", "")  # définis sur Render/Cloud pour protéger l’admin

os.makedirs(DATA_DIR, exist_ok=True)

# =======================
# UTILS
# =======================
@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        df = pd.read_csv(MATIERES_FILE).fillna("")
    else:
        df = pd.DataFrame(columns=["course_code", "course_title", "level_code", "track_code", "ec_type"])
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
            sheet = name[:31] or "Sheet1"
            df.to_excel(writer, index=False, sheet_name=sheet)
    bio.seek(0)
    return bio

# =======================
# SIDEBAR
# =======================
matieres_df = load_matieres()
st.sidebar.header("Navigation")
mode = st.sidebar.radio("Mode", ["Enseignant", "Admin"])

# =========================================================
# MODE ENSEIGNANT (NIVEAUX OBLIGATOIRES + PRIORITÉS UNIQUES)
# =========================================================
if mode == "Enseignant":
    st.title("🎓 Plateforme de choix des matières")
    st.caption("Département de Génie Civil")

    # --- Identité ---
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

    # --- Filtres d'affichage (NIVEAUX OBLIGATOIRES) ---
    st.subheader("🎚️ Filtres d'affichage")

    # Ordre de référence (adapte-le à ta maquette)
    ORDRE_NIVEAUX = ["Ingénieur_1", "Ingénieur_2", "Ingénieur_3", "L2", "L3", "M1", "M2"]

    presents = matieres_df["level_code"].dropna().unique().tolist()
    niveaux_obligatoires = [n for n in ORDRE_NIVEAUX if n in presents] + [n for n in presents if n not in ORDRE_NIVEAUX]

    st.markdown("**📘 Niveaux obligatoires (≥ 1 matière par niveau)**")
    st.markdown(
        " ".join(
            [
                f"<span style='background:#eef2ff;padding:4px 10px;border-radius:12px;margin-right:6px;display:inline-block'>{n}</span>"
                for n in niveaux_obligatoires
            ]
        ),
        unsafe_allow_html=True,
    )
    # Verrouillage : on impose tous les niveaux
    niveaux_sel = niveaux_obligatoires[:]

    # Parcours présents dans ces niveaux (restent filtrables)
    parcours_all = sorted(
        matieres_df[matieres_df["level_code"].isin(niveaux_sel)]["track_code"].dropna().unique().tolist()
    )
    parcours_sel = st.multiselect("🎯 Parcours à inclure", options=parcours_all, default=parcours_all)

    # Types d'EC (optionnel)
    ec_types_all = sorted(matieres_df["ec_type"].dropna().unique().tolist())
    ec_types_sel = st.multiselect("🧩 Types d'EC (facultatif)", options=ec_types_all, default=ec_types_all)

    # Jeu de données filtré global
    filtre = (
        (matieres_df["level_code"].isin(niveaux_sel)) &
        (matieres_df["track_code"].isin(parcours_sel)) &
        (matieres_df["ec_type"].isin(ec_types_sel))
    )
    filtré = matieres_df.loc[filtre, ["course_code","course_title","level_code","track_code","ec_type"]].copy()

    if filtré.empty:
        st.info("Aucune matière pour ce filtre.")
        st.stop()

    st.subheader(f"📚 Catalogue filtré ({len(filtré)})")
    st.dataframe(filtré, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("✅ Sélection & priorités")

    # Tableau éditable (case à cocher + priorité)
    work = filtré.copy()
    work["Choisir"] = False
    work["Priorité"] = None

    edited = st.data_editor(
        work,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "Choisir": st.column_config.CheckboxColumn("Choisir"),
            "Priorité": st.column_config.NumberColumn(
                "Priorité", min_value=1, step=1,
                help="Classement 1 = priorité maximale. Priorités **uniques** sur l'ensemble."
            ),
        },
    )

    remarque = st.text_area(
        "📝 Recommandations / Remarques / Préférences EDT",
        placeholder="Ex. : éviter lundi matin ; préférence TD L3 ; binôme souhaité…",
        height=120,
    )

    MIN_TOTAL = 8  # règle globale

    # --- Validation ---
    chosen = edited[edited["Choisir"] == True].copy()
    erreurs = []

    # total ≥ 8
    if len(chosen) < MIN_TOTAL:
        erreurs.append(f"Vous devez choisir au moins **{MIN_TOTAL} matières** (actuellement {len(chosen)}).")

    # ≥ 1 par niveau obligatoire
    manquants = [lvl for lvl in niveaux_sel if lvl not in chosen["level_code"].unique()]
    if manquants:
        erreurs.append("Niveaux sans choix : " + ", ".join([f"**{m}**" for m in manquants]) + " (min. 1 par niveau).")

    # priorités renseignées et uniques
    if not chosen.empty:
        if not chosen["Priorité"].notna().all():
            erreurs.append("Renseignez une **priorité** pour chaque matière sélectionnée.")
        else:
            prios = chosen["Priorité"].astype(int).tolist()
            if len(set(prios)) != len(prios):
                erreurs.append("Les **priorités doivent être uniques** (1, 2, 3, …).")

    if st.button("💾 Enregistrer mes choix", type="primary"):
        if not nom.strip() or not prenom.strip():
            st.error("Veuillez renseigner votre nom et votre prénom.")
            st.stop()
        if erreurs:
            st.error("Veuillez corriger :\n- " + "\n- ".join(erreurs))
            st.stop()

        # Enregistrement
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lignes = []
        chosen = chosen.sort_values("Priorité")
        for _, r in chosen.iterrows():
            lignes.append({
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "niveau": r["level_code"],
                "parcours": r["track_code"],
                "matiere": r["course_title"],
                "priorite": int(r["Priorité"]),
                "remarques": remarque,
                "date_soumission": now,
            })
        df_new = pd.DataFrame(lignes)
        save_soumissions(df_new)

        st.success("✅ Vos choix ont été enregistrés.")
        st.download_button(
            "📥 Télécharger mon récapitulatif (CSV)",
            data=df_new.to_csv(index=False).encode("utf-8"),
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
        enseignants_list = (df["nom"].fillna("") + " " + df["prenom"].fillna("")).str.strip()
        sel_prof = st.multiselect("Enseignants", sorted(enseignants_list.unique().tolist()))

    filtered = df.copy()
    if sel_niv: filtered = filtered[filtered["niveau"].isin(sel_niv)]
    if sel_par: filtered = filtered[filtered["parcours"].isin(sel_par)]
    if sel_prof:
        full = (filtered["nom"].fillna("") + " " + filtered["prenom"].fillna("")).str.strip().isin(sel_prof)
        filtered = filtered[full]

    st.subheader(f"📋 Soumissions ({len(filtered)})")
    st.dataframe(
        filtered.sort_values(["date_soumission","priorite"], ascending=[False, True]),
        use_container_width=True, hide_index=True
    )

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
            agg_prof = filtered.assign(enseignant=(filtered["nom"].fillna("") + " " + filtered["prenom"].fillna("")).str.strip())\
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
    st.download_button(
        "⬇️ Export Excel (toutes vues)",
        xls.getvalue(),
        file_name="voeux_admin_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.caption("Astuce : définis la variable d’environnement **ADMIN_PASS** sur Render/Cloud pour protéger l’accès.")
