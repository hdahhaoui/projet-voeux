import os
from io import BytesIO
from datetime import datetime
import zipfile
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Choix des matières - Département Génie Civil",
                   page_icon="🏗️", layout="wide")

DATA_DIR = os.getenv("DATA_PATH", "data")
MATIERES_FILE = os.path.join(DATA_DIR, "matieres_all.csv")
SOUMISSIONS_FILE = os.path.join(DATA_DIR, "soumissions.csv")
ADMIN_PASS = os.getenv("ADMIN_PASS", "gc2025s2")  # mot de passe par défaut

os.makedirs(DATA_DIR, exist_ok=True)


@st.cache_data
def load_matieres():
    if os.path.exists(MATIERES_FILE):
        return pd.read_csv(MATIERES_FILE).fillna("")
    return pd.DataFrame(columns=["course_code","course_title","level_code","track_code","ec_type"])

def load_soumissions():
    if os.path.exists(SOUMISSIONS_FILE):
        return pd.read_csv(SOUMISSIONS_FILE).fillna("")
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
    """Excel via XlsxWriter; ImportError si moteur indisponible."""
    try:
        import xlsxwriter  # noqa: F401
        bio = BytesIO()
        with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
            for name, df in sheets.items():
                df.to_excel(writer, index=False, sheet_name=(name[:31] or "Sheet1"))
        bio.seek(0)
        return bio
    except Exception as e:
        raise ImportError("xlsxwriter manquant") from e

def zip_csv_bytes(**sheets):
    bio = BytesIO()
    with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, df in sheets.items():
            zf.writestr(f"{name}.csv", df.to_csv(index=False).encode("utf-8"))
    bio.seek(0)
    return bio


matieres_df = load_matieres()


st.sidebar.header("Navigation")
mode = st.sidebar.radio("Mode", ["Enseignant", "Admin"])


def page_enseignant():
    st.title("🎓 Plateforme de choix des matières")
    st.caption("Département de Génie Civil")

    # Identité
    st.header("👩‍🏫 Informations personnelles")
    c1, c2 = st.columns(2)
    with c1:
        nom = st.text_input("Nom")
    with c2:
        prenom = st.text_input("Prénom")
    email = st.text_input("Adresse e-mail universitaire (facultatif)")

    st.divider()

    if matieres_df.empty:
        st.warning("⚠️ Le fichier 'data/matieres_all.csv' est introuvable ou vide.")
        return

    # Niveaux & parcours obligatoires
    st.subheader("🎚️ Filtres d'affichage")

    ORDRE_NIVEAUX = ["Ingénieur_1","Ingénieur_2","Ingénieur_3","L2","L3","M1","M2"]
    presents = matieres_df["level_code"].dropna().unique().tolist()
    niveaux_obligatoires = [n for n in ORDRE_NIVEAUX if n in presents] + [n for n in presents if n not in ORDRE_NIVEAUX]
    niveaux_sel = niveaux_obligatoires[:]

    st.markdown("**📘 Niveaux obligatoires (≥ 1 matière par niveau)**")
    st.markdown(" ".join([f"<span style='background:#eef2ff;padding:4px 10px;border-radius:12px;margin-right:6px;'>{n}</span>"
                          for n in niveaux_sel]), unsafe_allow_html=True)

    ORDER_TRACKS = ["Génie Civil","Structures","VOA","RIB"]
    present_tracks = matieres_df[matieres_df["level_code"].isin(niveaux_sel)]["track_code"].dropna().unique().tolist()
    parcours_sel = [t for t in ORDER_TRACKS if t in present_tracks] + [t for t in present_tracks if t not in ORDER_TRACKS]

    st.markdown("**🎯 Parcours obligatoires (≥ 1 matière par parcours)**")
    st.markdown(" ".join([f"<span style='background:#fee2e2;padding:4px 10px;border-radius:12px;margin-right:6px;'>{t}</span>"
                          for t in parcours_sel]), unsafe_allow_html=True)

    ec_types_all = sorted(matieres_df["ec_type"].dropna().unique().tolist())
    ec_types_sel = st.multiselect("🧩 Types d'EC (facultatif)", options=ec_types_all, default=ec_types_all)

    mask = (
        matieres_df["level_code"].isin(niveaux_sel) &
        matieres_df["track_code"].isin(parcours_sel) &
        matieres_df["ec_type"].isin(ec_types_sel)
    )
    catalogue = matieres_df.loc[mask, ["course_code","course_title","level_code","track_code","ec_type"]].copy()

    if catalogue.empty:
        st.info("Aucune matière trouvée avec ces critères.")
        return

    st.caption(f"{len(catalogue)} matières correspondent à vos filtres.")

    # Sélections & priorités (qualitatives)
    st.markdown("---")
    st.subheader("✅ Sélection & priorités")

    # Mise en forme de la grille : on garde un identifiant pour piloter les priorités.
    affichage_cols = {
        "course_code": "Code UE",
        "course_title": "Matière",
        "level_code": "Niveau",
        "track_code": "Parcours",
        "ec_type": "Type d'EC",
    }
    work = catalogue.rename(columns=affichage_cols).copy()

    # État persistant des priorités pour éviter les doubles clics dans la grille.
    # Gestion d'état : on garde séparément la liste des codes sélectionnés pour éviter
    # les doubles clics lorsque la table se rerend.
    priorites_state = st.session_state.setdefault("priorites", {})
    selection_codes = st.session_state.setdefault("selection_codes", list(priorites_state.keys()))

    # Nettoyage des sélections/priorités qui ne sont plus présentes dans le catalogue
    # courant (ex. après un changement de filtre).
    codes_disponibles = set(work["Code UE"].tolist())
    selection_codes = [code for code in selection_codes if code in codes_disponibles]
    priorites_state = {code: priorites_state.get(code, "") for code in selection_codes}

    st.session_state["selection_codes"] = selection_codes
    st.session_state["priorites"] = priorites_state

    work["Choisir"] = work["Code UE"].isin(selection_codes)
    work["Priorité"] = work["Code UE"].map(priorites_state).fillna("")

    st.markdown(
        """
        <style>
        /* Scrollbar plus visible et capsule d'indication pour la grille des matières */
        div[data-testid="stDataFrame"] div[data-testid="stDataFrameScrollableContainer"],
        div[data-testid="stDataFrame"] div[data-testid="StyledDataFrameContainer"] {
            scrollbar-width: thin;
            scrollbar-color: #4f46e5 #ede9fe;
            border-radius: 14px;
            box-shadow: inset 0 0 0 1px #e2e8f0;
        }
        div[data-testid="stDataFrame"] div[data-testid="stDataFrameScrollableContainer"]::-webkit-scrollbar,
        div[data-testid="stDataFrame"] div[data-testid="StyledDataFrameContainer"]::-webkit-scrollbar {
            width: 12px;
        }
        div[data-testid="stDataFrame"] div[data-testid="stDataFrameScrollableContainer"]::-webkit-scrollbar-thumb,
        div[data-testid="stDataFrame"] div[data-testid="StyledDataFrameContainer"]::-webkit-scrollbar-thumb {
            background-color: #4f46e5;
            border-radius: 999px;
            border: 3px solid #ede9fe;
        }
        div[data-testid="stDataFrame"] div[data-testid="stDataFrameScrollableContainer"]::-webkit-scrollbar-track,
        div[data-testid="stDataFrame"] div[data-testid="StyledDataFrameContainer"]::-webkit-scrollbar-track {
            background-color: #f5f3ff;
            border-radius: 999px;
        }
        div[data-testid="stDataFrame"] div[data-testid="stDataFrameScrollableContainer"]::after,
        div[data-testid="stDataFrame"] div[data-testid="StyledDataFrameContainer"]::after {
            content: "⬇️ Faites défiler pour découvrir toutes les matières";
            position: sticky;
            bottom: 8px;
            right: 16px;
            display: inline-flex;
            background: rgba(79, 70, 229, 0.92);
            color: white;
            font-size: 0.75rem;
            font-weight: 500;
            padding: 4px 14px;
            border-radius: 999px;
            box-shadow: 0 6px 18px rgba(79, 70, 229, 0.35);
            pointer-events: none;
            z-index: 5;
        }
        /* Mise en valeur du titre de colonne Priorité */
        div[data-testid="stDataFrame"] thead th:last-child {
            background: #eef2ff;
            color: #312e81;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    liste_priorites = [
        "🌟 Fortement souhaité",
        "👍 Souhaité",
        "🧩 Je prends le défi",
        "⚙️ Disponible si besoin",
    ]

    edited = st.data_editor(
        work,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="table_matieres",
        column_config={
            "Code UE": st.column_config.TextColumn("Code", help="Identifiant de la matière"),
            "Matière": st.column_config.TextColumn("Matière"),
            "Niveau": st.column_config.TextColumn("Niveau"),
            "Parcours": st.column_config.TextColumn("Parcours"),
            "Type d'EC": st.column_config.TextColumn("Type d'EC"),
            "Choisir": st.column_config.CheckboxColumn("Choisir"),
            "Priorité": st.column_config.TextColumn(
                "Priorité",
                help="La priorité se choisit dans le panneau ci-dessous pour un clic unique.",
                disabled=True,
            ),
        },
    )

    st.markdown(
        """
        <div style="display:flex;gap:0.75rem;align-items:center;margin:0.5rem 0 1.25rem;">
            <span style="font-size:1.2rem;">💡</span>
            <span style="font-size:0.95rem;">Sélectionnez vos matières dans la colonne <strong>Choisir</strong>,
            puis attribuez leur priorité via le panneau coloré juste en dessous (un simple clic suffit).</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selectionnees = edited[edited["Choisir"] == True].copy()
    codes_selectionnes = selectionnees["Code UE"].tolist()

    if codes_selectionnes != st.session_state.get("selection_codes", []):
        st.session_state["selection_codes"] = codes_selectionnes

    # Nettoyage des priorités qui ne sont plus nécessaires et synchronisation avec la
    # nouvelle sélection.
    priorites_state = st.session_state.get("priorites", {})
    priorites_state = {code: priorites_state.get(code, "") for code in codes_selectionnes}
    st.session_state["priorites"] = priorites_state

    active_select_keys = {f"prio_{code}" for code in codes_selectionnes}
    for key in list(st.session_state.keys()):
        if key.startswith("prio_") and key not in active_select_keys:
            del st.session_state[key]

    if not selectionnees.empty:
        st.markdown("#### 🎯 Priorisez vos matières sélectionnées")
        with st.container(border=True):
            for _, ligne in selectionnees.iterrows():
                code = ligne["Code UE"]
                nom = ligne["Matière"]
                niveau = ligne["Niveau"]
                parcours = ligne["Parcours"]
                etiquette = f"{nom} — {niveau} / {parcours}"
                valeur_actuelle = st.session_state["priorites"].get(code, "")
                choix = st.selectbox(
                    etiquette,
                    options=[""] + liste_priorites,
                    index=([""] + liste_priorites).index(valeur_actuelle) if valeur_actuelle in liste_priorites else 0,
                    key=f"prio_{code}",
                    help="Choisissez la priorité sans double clic",
                )
                st.session_state["priorites"][code] = choix
        selectionnees["Priorité"] = selectionnees["Code UE"].map(st.session_state["priorites"]).fillna("")
    else:
        st.info("Cochez une matière pour activer le choix de priorité.")

    # Reprojection des noms de colonnes d'origine pour la suite des validations
    inverse_cols = {v: k for k, v in affichage_cols.items()}
    selectionnees = selectionnees.rename(columns=inverse_cols) if not selectionnees.empty else selectionnees

    remarque = st.text_area("📝 Recommandations / Remarques / Préférences EDT",
                            placeholder="Ex. : éviter lundi matin ; éviter 15h30-17h00 …", height=120)

    MIN_TOTAL = 8
    chosen = selectionnees.copy()
    if "Choisir" in chosen.columns:
        chosen = chosen.drop(columns=["Choisir"])
    erreurs = []

    if len(chosen) < MIN_TOTAL:
        erreurs.append(f"Vous devez choisir au moins **{MIN_TOTAL} matières** (actuellement {len(chosen)}).")

    manquants_niv = [lvl for lvl in niveaux_sel if lvl not in chosen["level_code"].unique()]
    if manquants_niv:
        erreurs.append("Niveaux sans choix : " + ", ".join([f"**{m}**" for m in manquants_niv]) + " (min. 1 par niveau).")

    manquants_track = [t for t in parcours_sel if t not in chosen["track_code"].unique()]
    if manquants_track:
        erreurs.append("Parcours sans choix : " + ", ".join([f"**{t}**" for t in manquants_track]) + " (min. 1 par parcours).")

    if not chosen.empty and (chosen["Priorité"] == "").any():
        erreurs.append("Choisissez une **priorité** dans le panneau dédié pour chaque matière sélectionnée.")

    if st.button("💾 Enregistrer mes choix", type="primary"):
        if not nom.strip() or not prenom.strip():
            st.error("Veuillez renseigner votre nom et votre prénom.")
            return
        if erreurs:
            st.error("⚠️ Corrigez :\n- " + "\n- ".join(erreurs))
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lignes = []
        # tri : on garde l'ordre de la liste_priorites
        cat_order = {v:i for i, v in enumerate(liste_priorites)}
        chosen = chosen.sort_values("Priorité", key=lambda s: s.map(cat_order))

        for _, r in chosen.iterrows():
            lignes.append({
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "niveau": r["level_code"],
                "parcours": r["track_code"],
                "matiere": r["course_title"],
                "priorite": r["Priorité"],
                "remarques": remarque,
                "date_soumission": now,
            })
        df_new = pd.DataFrame(lignes)
        save_soumissions(df_new)

        st.success("✅ Vos choix ont été enregistrés.")
        st.download_button("📥 Télécharger mon récapitulatif (CSV)",
                           data=df_new.to_csv(index=False).encode("utf-8"),
                           file_name=f"choix_{nom}_{prenom}.csv",
                           mime="text/csv")


def page_admin():
    st.title("🛠️ Administration – Vœux enseignants")

    if ADMIN_PASS:
        code = st.text_input("Code admin", type="password")
        if code != ADMIN_PASS:
            st.info("Entrez le code admin pour accéder aux données.")
            return

    df = load_soumissions()
    if df.empty:
        st.warning("Aucune soumission pour l’instant.")
        return

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
    st.dataframe(filtered.sort_values(["date_soumission","priorite"], ascending=[False, True]),
                 use_container_width=True, hide_index=True)

    st.subheader("📊 Synthèses")
    cA, cB, cC = st.columns(3)
    with cA:
        agg_niv = filtered.groupby("niveau").size().reset_index(name="nb_voeux")
        st.caption("Par niveau"); st.dataframe(agg_niv, use_container_width=True, hide_index=True)
    with cB:
        agg_mat = filtered.groupby("matiere").size().reset_index(name="nb_voeux").sort_values("nb_voeux", ascending=False)
        st.caption("Top matières"); st.dataframe(agg_mat, use_container_width=True, hide_index=True)
    with cC:
        agg_prof = filtered.assign(enseignant=(filtered["nom"].fillna("") + " " + filtered["prenom"].fillna("")).str.strip()) \
                           .groupby("enseignant").size().reset_index(name="nb_voeux") \
                           .sort_values("nb_voeux", ascending=False)
        st.caption("Par enseignant"); st.dataframe(agg_prof, use_container_width=True, hide_index=True)

    # Export
    sheets = dict(
        Soumissions=filtered.sort_values(["date_soumission","priorite"], ascending=[False, True]),
        Par_niveau=agg_niv,
        Top_matieres=agg_mat,
    )
    try:
        xls = to_excel_bytes(**sheets)
        st.download_button("⬇️ Export Excel (toutes vues)", xls.getvalue(),
                           file_name="voeux_admin_export.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except ImportError:
        zipbuf = zip_csv_bytes(**sheets)
        st.download_button("⬇️ Export (ZIP de CSV – moteur Excel absent)", zipbuf.getvalue(),
                           file_name="voeux_admin_export.zip", mime="application/zip")


if mode == "Enseignant":
    page_enseignant()
else:
    page_admin()
