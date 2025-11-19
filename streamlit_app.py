import os

import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

# ============================
# configuración de la app
# ============================
st.set_page_config(
    page_title='Emisiones de CO₂ en el Mundo',
    layout='wide'
)

BASE_DIR = os.path.dirname(__file__)
SHP_PATH = os.path.join(BASE_DIR, '50m_cultural', 'ne_50m_admin_0_countries.shp')
CSV_PATH = os.path.join(BASE_DIR, 'emissions_per_country', 'annual-co2-emissions-per-country.csv')

# ============================
# carga de datos
# ============================
@st.cache_data
def load_world(shp_path: str):
    if not os.path.exists(shp_path):
        raise FileNotFoundError(f"No se encontró el shapefile: {shp_path}")

    world = gpd.read_file(shp_path)
    world = world.rename(columns={'ISO_A3': 'code', 'NAME': 'country'})
    world['code'] = world['code'].str.upper()

    world_master = (
        world[['code', 'country', 'geometry']]
        .drop_duplicates(subset=['code'])
        .set_index('code')
    )

    geojson_world = world_master['geometry'].__geo_interface__
    return world_master, geojson_world


@st.cache_data
def load_emissions(csv_path: str):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"No se encontró el csv: {csv_path}")

    df = pd.read_csv(csv_path)
    df = df.rename(columns={'Entity': 'country', 'Code': 'code', 'Year': 'year'})
    df['code'] = df['code'].str.upper()

    df = df[df['code'].str.len() == 3]

    value_col = [c for c in df.columns if c not in ['country', 'code', 'year']]
    df = df.rename(columns={value_col[0]: 'co2'})

    return df[['country', 'code', 'year', 'co2']]


# ============================
# mapa de CO2
# ============================
def make_co2_map(df_co2, world_master, geojson_world, year):
    co2_year = (
        df_co2[df_co2['year'] == year][['code', 'co2']]
        .groupby('code', as_index=False)
        .agg({'co2': 'sum'})
        .set_index('code')
    )

    world_y = world_master.join(co2_year, how='left')
    g_with = world_y[world_y['co2'].notna()].reset_index()
    g_no = world_y[world_y['co2'].isna()].reset_index()

    fig = px.choropleth(
        g_with,
        geojson=geojson_world,
        locations='code',
        color='co2',
        hover_name='country',
        color_continuous_scale='Reds',
        projection='natural earth',
        labels={'co2': 'Emisiones de CO₂ (toneladas)'}
    )

    if not g_no.empty:
        fig_grey = px.choropleth(
            g_no,
            geojson=geojson_world,
            locations='code',
            color_discrete_sequence=['#d0d0d0'],
            hover_name='country',
            projection='natural earth'
        )
        for trace in fig_grey.data:
            trace.showlegend = False
            fig.add_trace(trace)

    fig.update_geos(fitbounds='locations', visible=False)
    fig.update_layout(
        title=f"Emisiones de CO₂ por país en {year}",
        title_x=0.5,
        height=600
    )

    return fig


# ============================
# app principal
# ============================
def main():
    st.title("Explorador interactivo de emisiones de CO₂")
    st.markdown(
        """
        Esta aplicación permite explorar la evolución histórica de las emisiones
        de dióxido de carbono (CO₂) a nivel global y por país, utilizando datos
        de **Our World In Data** (Global Carbon Budget).
        """
    )

    # cargar datos
    world_master, geojson_world = load_world(SHP_PATH)
    df_co2 = load_emissions(CSV_PATH)

    # sidebar
    st.sidebar.header("Controles")
    min_year = int(df_co2['year'].min())
    max_year = int(df_co2['year'].max())

    years_special = [1751, 1851, 1951, 2000, 2024]
    years_special = [y for y in years_special if min_year <= y <= max_year]

    preset = st.sidebar.selectbox(
        "Años destacados",
        ["Ninguno"] + [str(y) for y in years_special]
    )

    year_default = int(preset) if preset != "Ninguno" else max_year

    year = st.sidebar.slider(
        "Selecciona un año",
        min_value=min_year,
        max_value=max_year,
        value=year_default
    )

    # tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🌍 Mapa global", "🇺🇳 Comparación de países", "📈 Tendencias globales", "ℹ️ Acerca de los datos"]
    )

    # ---------------- TAB 1: MAPA ----------------
    with tab1:
        st.subheader("Mapa global de emisiones")
        fig = make_co2_map(df_co2, world_master, geojson_world, year)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            """
            **Nota:** Los países en gris no tienen datos para el año seleccionado.
            """
        )

        st.markdown("---")
        st.subheader(f"Emisiones por país en {year}")

        df_year = (
            df_co2[df_co2['year'] == year][['country', 'code', 'co2']]
            .groupby(['country', 'code'], as_index=False)
            .agg({'co2': 'sum'})
            .sort_values('co2', ascending=False)
        )

        st.dataframe(df_year, use_container_width=True)

    # ---------------- TAB 2: COMPARACIÓN ----------------
    with tab2:
        st.subheader("Comparación entre países")

        countries = sorted(df_co2['country'].unique())
        default_countries = [p for p in ['China', 'United States', 'India'] if p in countries]

        selected = st.multiselect("Selecciona países", countries, default=default_countries)

        year_range = st.slider(
            "Rango de años",
            min_value=min_year,
            max_value=max_year,
            value=(1960, max_year)
        )

        metric = st.radio(
            "Tipo de métrica",
            ["Emisiones absolutas", "Participación global (%)"]
        )

        df_range = df_co2[
            (df_co2['country'].isin(selected)) &
            (df_co2['year'].between(year_range[0], year_range[1]))
        ].copy()

        if df_range.empty:
            st.warning("Selecciona países y un rango válido.")
        else:
            if metric == "Participación global (%)":
                df_global = df_co2.groupby("year", as_index=False).agg({"co2": "sum"})
                df_global = df_global.rename(columns={"co2": "co2_global"})
                df_range = df_range.merge(df_global, on="year", how="left")
                df_range["share"] = (df_range["co2"] / df_range["co2_global"]) * 100

                fig_c = px.line(
                    df_range,
                    x="year",
                    y="share",
                    color="country",
                    labels={"share": "Participación (%)"},
                    title="Participación en las emisiones globales"
                )
            else:
                fig_c = px.line(
                    df_range,
                    x="year",
                    y="co2",
                    color="country",
                    labels={"co2": "Emisiones de CO₂"},
                    title="Emisiones anuales por país"
                )

            st.plotly_chart(fig_c, use_container_width=True)

            st.markdown("---")
            st.subheader(f"Top 10 emisores en {year}")

            df_rank = (
                df_co2[df_co2['year'] == year][["country", "co2"]]
                .groupby("country", as_index=False).sum()
                .sort_values("co2", ascending=False)
                .head(10)
            )

            fig_top = px.bar(
                df_rank,
                x="co2",
                y="country",
                orientation="h",
                title=f"Top 10 emisores ({year})"
            )
            fig_top.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig_top, use_container_width=True)

    # ---------------- TAB 3: TENDENCIAS ----------------
    with tab3:
        st.subheader("Tendencias globales de CO₂")

        df_global = (
            df_co2.groupby('year', as_index=False)
            .agg({'co2': 'sum'})
            .sort_values('year')
        )

        fig_g = px.line(
            df_global,
            x="year",
            y="co2",
            labels={"co2": "Emisiones globales"},
            title="Emisiones globales de CO₂ a lo largo del tiempo"
        )

        st.plotly_chart(fig_g, use_container_width=True)

    # ---------------- TAB 4: INFO ----------------
    with tab4:
        st.subheader("Acerca de los datos")
        st.markdown(
            """
            **Fuente:**  
            Global Carbon Budget (2025), con procesamiento de *Our World in Data*.

            **Unidades:**  
            Toneladas de CO₂ emitidas por año.

            **Decisiones de diseño:**  
            - Países sin datos se muestran en gris.  
            - Escala continua de rojos para asociar mayor emisión con mayor intensidad.  
            - El año controla tanto el mapa como el ranking.

            **Limitaciones:**  
            - No todos los países tienen datos completos.  
            - Las emisiones son territoriales (no ajustadas por consumo).
            """
        )


if __name__ == "__main__":
    main()
