import os

import pandas as pd
import plotly.express as px
import streamlit as st

# ============================
# Configuración de la app
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
# Carga y preparación de datos
# ============================
@st.cache_data
def load_emissions(csv_path: str) -> pd.DataFrame:
    """Carga el CSV de emisiones y lo deja listo para usar."""
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

    # En OWID, la columna `co2` está en millones de toneladas
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
        labels={"co2": "Emisiones de CO₂ (millones de toneladas)"},
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
# App principal
# ============================
def main():
    st.title("Explorador interactivo de emisiones de CO₂")
    st.markdown(
        """
        Esta aplicación permite explorar la evolución histórica de las
        emisiones de dióxido de carbono (CO₂) a nivel global y por país,
        utilizando datos de **Our World In Data** basados en el
        **Global Carbon Budget**.
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
    tab_mapa, tab_paises, tab_tendencias, tab_ranking, tab_info = st.tabs(
        [
            "🌍 Mapa global",
            "🇺🇳 Comparación de países",
            "📈 Tendencias globales",
            "🏅 Ranking y desigualdad",
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
        st.markdown(
            """
            Esta sección se inspira en las comparaciones de emisiones por país
            de Our World In Data. Permite ver cómo han evolucionado los
            principales emisores a lo largo del tiempo y cuál es su peso
            relativo en las emisiones globales.
            """
        )

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
                        "co2": "Emisiones de CO₂ (millones de toneladas)",
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
                    "co2": "Emisiones de CO₂ (millones de toneladas)",
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
                "co2": "Emisiones globales de CO₂ (millones de toneladas)",
            },
            title="Emisiones globales de CO₂ a lo largo del tiempo",
        )

        st.plotly_chart(fig_global, use_container_width=True)

        st.markdown(
            """
            Esta curva permite observar cómo las emisiones globales se
            mantienen relativamente bajas hasta la Revolución Industrial y luego
            crecen de forma muy acelerada durante el siglo XX, con algunas
            desaceleraciones asociadas a crisis económicas o eventos globales.
            """
        )
        
    # ========== TAB 4: RANKING Y DESIGUALDAD ==========
    with tab_ranking:
        st.subheader("Evolución del ranking de emisiones por país")

        st.markdown(
            """
            Este gráfico muestra cómo cambia el lugar que ocupa cada país en el
            ranking de emisiones a lo largo del tiempo. Es un ejemplo de
            *bump chart*: usamos posición vertical (uno de los canales más
            precisos) para codificar el ranking, y color para identificar
            países, tal como se discute en la clase sobre marcas y canales.
            """
        )

        countries_rank = sorted(df_co2["country"].unique())
        default_countries_rank = [
            p for p in ["China", "United States", "India", "European Union (27)"] if p in countries_rank
        ]

        selected_rank = st.multiselect(
            "Selecciona países para seguir su posición en el ranking",
            options=countries_rank,
            default=default_countries_rank,
            key="rank_multiselect",
        )

        year_range_rank = st.slider(
            "Rango de años para el ranking",
            min_value=min_year,
            max_value=max_year,
            value=(1960, max_year),
            step=1,
            key="rank_year_range",
        )

        # calcular ranking por año
        df_rank_evol = (
            df_co2[
                df_co2["year"].between(year_range_rank[0], year_range_rank[1])
            ][["year", "country", "co2"]]
            .groupby(["year", "country"], as_index=False)
            .agg({"co2": "sum"})
        )

        df_rank_evol["rank"] = (
            df_rank_evol
            .groupby("year")["co2"]
            .rank(ascending=False, method="min")
        )

        df_rank_sel = df_rank_evol[df_rank_evol["country"].isin(selected_rank)]

        if df_rank_sel.empty or not selected_rank:
            st.warning("Selecciona al menos un país y un rango de años válido para ver el ranking.")
        else:
            fig_bump = px.line(
                df_rank_sel,
                x="year",
                y="rank",
                color="country",
                markers=True,
                labels={
                    "year": "Año",
                    "rank": "Posición en el ranking (1 = mayor emisor)",
                    "country": "País",
                },
                title="Bump chart: evolución del ranking de emisiones",
            )
            # en un ranking, 1 es mejor arriba → invertimos el eje Y
            fig_bump.update_yaxes(autorange="reversed", dtick=1)

            st.plotly_chart(fig_bump, use_container_width=True)

        st.markdown("---")
        st.subheader("Desigualdad en las emisiones entre países (curva tipo Lorenz)")

        st.markdown(
            """
            Aquí se muestra una curva similar a la de Lorenz: ordenamos los países
            desde los que menos emiten a los que más emiten, y calculamos la
            fracción acumulada de países versus la fracción acumulada de emisiones.
            Si todos emitieran lo mismo, la curva sería una diagonal perfecta.
            Mientras más se aleja de la diagonal, mayor desigualdad en las emisiones.
            """
        )

        # usamos el mismo año seleccionado en el sidebar
        df_year_all = (
            df_co2[df_co2["year"] == year][["country", "co2"]]
            .groupby("country", as_index=False)
            .agg({"co2": "sum"})
        )

        df_year_pos = df_year_all[df_year_all["co2"] > 0].copy()
        if df_year_pos.empty:
            st.info("No hay datos positivos de emisiones para construir la curva en este año.")
        else:
            df_year_pos = df_year_pos.sort_values("co2")
            n = len(df_year_pos)
            df_year_pos["country_share"] = pd.Series(range(1, n + 1), dtype=float) / n
            df_year_pos["emissions_cum_share"] = df_year_pos["co2"].cumsum() / df_year_pos["co2"].sum()


            fig_lorenz = px.line(
                df_year_pos,
                x="country_share",
                y="emissions_cum_share",
                labels={
                    "country_share": "Fracción acumulada de países",
                    "emissions_cum_share": "Fracción acumulada de emisiones",
                },
                title=f"Curva tipo Lorenz de emisiones en {year}",
            )

            # línea de igualdad perfecta
            fig_lorenz.add_shape(
                type="line",
                x0=0, y0=0, x1=1, y1=1,
                line=dict(dash="dash")
            )

            fig_lorenz.update_xaxes(range=[0, 1])
            fig_lorenz.update_yaxes(range=[0, 1])

            st.plotly_chart(fig_lorenz, use_container_width=True)
    
    # ========== TAB 4: INFO ==========
    with tab_info:
        st.subheader("Acerca de los datos y decisiones de diseño")
        st.markdown(
            """
            **Datasets utilizados**

            - *Annual CO₂ emissions per country*  
              Fuente: Global Carbon Budget, compilado y publicado por
              [Our World In Data](https://ourworldindata.org/co2-emissions).  
              En el código se utiliza la columna `co2`, que corresponde a
              **emisiones anuales de CO₂ medidas en millones de toneladas**.

            **Unidades y cobertura**

            - Unidad: millones de toneladas de CO₂ emitidas por año.  
            - Cobertura temporal aproximada: desde mediados del siglo XVIII
              (alrededor de 1750) hasta años recientes, dependiendo del país.  
            - Cobertura espacial: países y algunas regiones agregadas
              (por ejemplo *World*, *Asia*, *Europe*).

            **Relación con las visualizaciones de Our World In Data**

            - El **mapa global** se inspira en los mapas de OWID de emisiones
              anuales por país, utilizando códigos ISO3 como llave de unión.  
            - Los gráficos de **series de tiempo por país** y **serie global**
              recrean la idea de analizar la evolución histórica de las
              emisiones tanto a nivel de país como para el total mundial.  
            - El **ranking de Top 10 emisores** retoma las comparaciones
              de mayores contribuyentes a las emisiones en un año dado.

            **Decisiones de diseño**

            - Se utiliza una escala continua de rojos en el mapa, asociando
              intuitivamente mayores emisiones con mayor intensidad de color.  
            - Los países sin dato para el año seleccionado se muestran sin
              color (gris claro), para diferenciarlos de valores reales
              cercanos a cero. Esta decisión se explica explícitamente en
              la pestaña del mapa.  
            - En la comparación de países se ofrecen dos métricas:
              emisiones absolutas (millones de toneladas) y participación
              en las emisiones globales (%), lo que permite analizar tanto
              el peso absoluto como el relativo de cada país.  
            - El mismo año seleccionado en el *sidebar* actualiza de forma
              consistente el mapa, la tabla y el ranking, manteniendo un
              estado compartido entre visualizaciones.

            **Limitaciones**

            - No todos los países cuentan con información para todos los años;
              algunos aparecen sin dato en periodos antiguos o recientes.  
            - Las emisiones utilizadas son territoriales (producción dentro
              de las fronteras del país), por lo que no están ajustadas por
              comercio internacional ni por consumo.  
            - Las emisiones de aviación y transporte internacional se
              contabilizan en el total global, pero no pueden asignarse de
              forma directa a un país específico.
            """
        )


if __name__ == "__main__":
    main()



