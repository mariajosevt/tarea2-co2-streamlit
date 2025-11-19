import os

import pandas as pd
import plotly.express as px
import streamlit as st

# ============================
# configuración de la app
# ============================
st.set_page_config(
    page_title="Emisiones de CO₂ en el Mundo",
    layout="wide"
)

BASE_DIR = os.path.dirname(__file__)
CSV_PATH = os.path.join(
    BASE_DIR,
    "emissions_per_country",
    "annual-co2-emissions-per-country.csv",
)

# ============================
# carga y preparación de datos
# ============================
@st.cache_data
def load_emissions(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encontró el csv: {csv_path}")

    df = pd.read_csv(csv_path)

    # estandarizar nombres
    df = df.rename(columns={"Entity": "country", "Code": "code", "Year": "year"})
    df["code"] = df["code"].astype(str).str.upper()

    # quedarnos solo con códigos iso3 válidos
    df = df[df["code"].str.len() == 3]

    # detectar columna de emisiones (la primera que no sea country/code/year)
    value_cols = [c for c in df.columns if c not in ["country", "code", "year"]]
    if not value_cols:
        raise ValueError("No se encontró columna de emisiones en el dataset.")

    df = df.rename(columns={value_cols[0]: "co2"})

    # limpiar valores
    df = df[~df["co2"].isna()].copy()
    df["year"] = df["year"].astype(int)

    return df[["country", "code", "year", "co2"]]


def make_co2_map(df_co2: pd.DataFrame, year: int):
    """Mapa mundial usando solo plotly (sin geopandas)."""
    df_year = (
        df_co2[df_co2["year"] == year][["country", "code", "co2"]]
        .groupby(["country", "code"], as_index=False)
        .agg({"co2": "sum"})
    )

    fig = px.choropleth(
        df_year,
        locations="code",
        color="co2",
        hover_name="country",
        color_continuous_scale="Reds",
        projection="natural earth",
        labels={"co2": "Emisiones de CO₂ (toneladas)"},
    )

    # países sin dato quedan por defecto en gris/claro en el mapa base
    fig.update_geos(showcountries=True, showcoastlines=False, showland=True)
    fig.update_layout(
        title=f"Emisiones de CO₂ por país en {year}",
        title_x=0.5,
        height=600,
    )
    return fig


# ============================
# app principal
# ============================
def main():
    st.title("Explorador interactivo de emisiones de CO₂")
    st.markdown(
        """
        Esta aplicación permite explorar la evolución histórica de las
        emisiones de dióxido de carbono (CO₂) a nivel global y por país,
        utilizando datos de **Our World In Data** (Global Carbon Budget).
        """
    )

    df_co2 = load_emissions(CSV_PATH)

    # sidebar
    st.sidebar.header("Controles")
    min_year = int(df_co2["year"].min())
    max_year = int(df_co2["year"].max())

    años_destacados = [1751, 1851, 1951, 2000, 2024]
    años_destacados = [a for a in años_destacados if min_year <= a <= max_year]

    preset = st.sidebar.selectbox(
        "Años destacados",
        ["Ninguno"] + [str(a) for a in años_destacados],
        index=0,
    )

    year_default = int(preset) if preset != "Ninguno" else max_year

    year = st.sidebar.slider(
        "Selecciona un año",
        min_value=min_year,
        max_value=max_year,
        value=year_default,
        step=1,
    )

    # tabs
    tab_mapa, tab_paises, tab_tendencias, tab_info = st.tabs(
        [
            "🌍 Mapa global",
            "🇺🇳 Comparación de países",
            "📈 Tendencias globales",
            "ℹ️ Acerca de los datos",
        ]
    )

    # ========== TAB 1: MAPA ==========
    with tab_mapa:
        st.subheader("Mapa global de emisiones de CO₂")
        fig_map = make_co2_map(df_co2, year)
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown(
            """
            Los países que no cuentan con datos para el año seleccionado
            aparecen sin color en el mapa de referencia (tono gris claro).
            Esto no implica que sus emisiones sean cero, sino ausencia de
            dato en el dataset.
            """
        )

        st.markdown("---")
        st.subheader(f"Emisiones por país en {year}")

        df_year = (
            df_co2[df_co2["year"] == year][["country", "code", "co2"]]
            .groupby(["country", "code"], as_index=False)
            .agg({"co2": "sum"})
            .sort_values("co2", ascending=False)
        )
        st.dataframe(df_year, use_container_width=True)

    # ========== TAB 2: COMPARACIÓN ==========
    with tab_paises:
        st.subheader("Comparación entre países")

        countries = sorted(df_co2["country"].unique())
        default_countries = [
            p for p in ["China", "United States", "India"] if p in countries
        ]

        selected = st.multiselect(
            "Selecciona uno o más países",
            options=countries,
            default=default_countries,
        )

        year_range = st.slider(
            "Rango de años",
            min_value=min_year,
            max_value=max_year,
            value=(1960, max_year),
            step=1,
        )

        metric = st.radio(
            "Tipo de métrica",
            ["Emisiones absolutas", "Participación global (%)"],
        )

        df_range = df_co2[
            (df_co2["country"].isin(selected))
            & (df_co2["year"].between(year_range[0], year_range[1]))
        ].copy()

        if df_range.empty or not selected:
            st.warning("Selecciona al menos un país y un rango de años válido.")
        else:
            if metric == "Participación global (%)":
                df_global = (
                    df_co2.groupby("year", as_index=False)
                    .agg({"co2": "sum"})
                    .rename(columns={"co2": "co2_global"})
                )
                df_range = df_range.merge(df_global, on="year", how="left")
                df_range["share"] = (df_range["co2"] / df_range["co2_global"]) * 100

                fig_comp = px.line(
                    df_range,
                    x="year",
                    y="share",
                    color="country",
                    labels={
                        "year": "Año",
                        "share": "Participación en emisiones globales (%)",
                        "country": "País",
                    },
                    title="Participación en las emisiones globales de CO₂",
                )
            else:
                fig_comp = px.line(
                    df_range,
                    x="year",
                    y="co2",
                    color="country",
                    labels={
                        "year": "Año",
                        "co2": "Emisiones de CO₂ (toneladas)",
                        "country": "País",
                    },
                    title="Emisiones anuales de CO₂ por país",
                )

            st.plotly_chart(fig_comp, use_container_width=True)

            st.markdown("---")
            st.subheader(f"Top 10 emisores en {year}")

            df_rank = (
                df_co2[df_co2["year"] == year][["country", "co2"]]
                .groupby("country", as_index=False)
                .agg({"co2": "sum"})
                .sort_values("co2", ascending=False)
                .head(10)
            )

            fig_top = px.bar(
                df_rank,
                x="co2",
                y="country",
                orientation="h",
                labels={
                    "co2": "Emisiones de CO₂ (toneladas)",
                    "country": "País",
                },
                title=f"Top 10 emisores en {year}",
            )
            fig_top.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig_top, use_container_width=True)

    # ========== TAB 3: TENDENCIAS ==========
    with tab_tendencias:
        st.subheader("Tendencias globales de CO₂")

        df_global = (
            df_co2.groupby("year", as_index=False)
            .agg({"co2": "sum"})
            .sort_values("year")
        )

        fig_global = px.line(
            df_global,
            x="year",
            y="co2",
            labels={
                "year": "Año",
                "co2": "Emisiones globales de CO₂ (toneladas)",
            },
            title="Emisiones globales de CO₂ a lo largo del tiempo",
        )

        st.plotly_chart(fig_global, use_container_width=True)

        st.markdown(
            """
            Esta curva permite observar cómo las emisiones globales se
            mantienen bajas hasta la Revolución Industrial y luego
            crecen de forma muy acelerada durante el siglo XX, con
            ligeras desaceleraciones asociadas a crisis económicas
            o eventos globales.
            """
        )

    # ========== TAB 4: INFO ==========
    with tab_info:
        st.subheader("Acerca de los datos y decisiones de diseño")
        st.markdown(
            """
            **Datos utilizados**

            - *Annual CO₂ emissions per country*  
              Fuente: Global Carbon Budget (Our World In Data).

            **Unidades y cobertura**

            - Emisiones anuales de CO₂, en toneladas.  
            - Cobertura temporal aproximada: 1750–2024 (según país).  
            - Cobertura espacial: países y algunas regiones agregadas.

            **Decisiones de diseño**

            - Se usa una escala continua de rojos para asociar visualmente
              mayor emisión con mayor intensidad de color.
            - El mismo año seleccionado controla tanto el mapa como la tabla
              y el ranking, para mantener consistencia.
            - La comparación de países permite cambiar entre emisiones
              absolutas y participación global, ofreciendo dos lecturas
              complementarias del mismo fenómeno.

            **Limitaciones**

            - Algunos países no cuentan con datos para todos los años.
            - Las emisiones son territoriales (no ajustadas por consumo
              ni comercio internacional).
            - Las emisiones de aviación y transporte internacional
              no se asignan fácilmente a países individuales.
            """
        )


if __name__ == "__main__":
    main()
