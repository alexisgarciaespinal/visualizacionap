from flask import Flask, render_template, request
import os
import plotly.express as px
import plotly.io as pio
from pymongo import MongoClient
import pandas as pd
import folium
from folium.plugins import MarkerCluster

app = Flask(__name__)

# Configurar conexión a MongoDB
app.secret_key = '0e01e4bcf2960bdb6aafeac4cded07b5f0bb809d8e1ff7e9'
client = MongoClient('mongodb+srv://alexisgarcia:Percha84@temporada2324.lug6z.mongodb.net/?retryWrites=true&w=majority&appName=temporada2324')
db = client['apacilagua']

collection = db['form_data']
estimaciones = db['estimaciones_data'] 
pulverizaciones = db['pulverizaciones_data']

# Ruta para la página de inicio
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ficha', methods=['GET', 'POST'])
def ficha():
    # Convertir los datos de MongoDB en DataFrame
    data = list(collection.find())
    df = pd.DataFrame(data)

    # Asegurar que 'Fecha/Hora' esté en formato datetime
    df['Fecha/Hora'] = pd.to_datetime(df['Fecha/Hora'], errors='coerce')

    ####################################
    # Gráfico de Líneas (Tensiometros)
    df_alex = df[['Fecha/Hora', 'Edad_cultivo', 'Lote', 'Tensiometro_12', 'Tensiometro_24']].dropna()

    lotes = df_alex['Lote'].unique()
    selected_lote = request.args.get('lote_lineas', default=lotes[0])  
    df_lote = df_alex[df_alex['Lote'] == selected_lote]

    # Crear columna combinada de Edad y Hora
    df_lote['Edad_Hora'] = df_lote['Edad_cultivo'].astype(str) + " ddt " + df_lote['Fecha/Hora'].dt.strftime('%H:%M')

    # Gráfico de líneas
    df_lineas = df_lote.melt(
        id_vars=['Edad_Hora', 'Lote'],
        value_vars=['Tensiometro_12', 'Tensiometro_24'],
        var_name='Tensiometro',
        value_name='Valor'
    )
    fig_lineas = px.line(
        df_lineas, 
        x='Edad_Hora', 
        y='Valor', 
        color='Tensiometro', 
        title=f'Datos Tensiometros por Lote: {selected_lote}', 
        labels={'Valor': 'Tensiometro', 'Edad_Hora': 'Edad (días y hora)'}, 
        markers=True
    )




    #######################################
    ##Grarico de puntos CE y PH del suelo
    try:
        # Recuperar los datos desde MongoDB
        datalu = list(collection.find())
        if not datalu:
            return render_template('prueba.html', message="No hay datos en la base de datos.")

        # Crear DataFrame con las columnas necesarias
        dfa = pd.DataFrame(datalu)[['Fecha/Hora', 'Turno', 'Valvula', 'Lote', 'CE_suelo', 'PH_suelo']]
        dfa['Fecha/Hora'] = pd.to_datetime(dfa['Fecha/Hora'], errors='coerce')
        dfa = dfa.dropna(subset=['CE_suelo', 'PH_suelo'])

        # Obtener los parámetros del request (selección del usuario)
        fecha_seleccionada = request.args.get('fecha')
        lote_seleccionado = request.args.get('lote')
        turno_seleccionado = request.args.get('turno')
        valvula_seleccionada = request.args.get('valvula')

        # Filtrar los datos progresivamente
        temp_df = dfa
        if fecha_seleccionada:
            temp_df = temp_df[temp_df['Fecha/Hora'].dt.date.astype(str) == fecha_seleccionada]

        if lote_seleccionado:
            temp_df = temp_df[temp_df['Lote'] == lote_seleccionado]

        if turno_seleccionado:
            temp_df = temp_df[temp_df['Turno'] == turno_seleccionado]

        if valvula_seleccionada:
            temp_df = temp_df[temp_df['Valvula'] == valvula_seleccionada]

        # Generar listas únicas basadas en los datos filtrados progresivamente
        fechas_unicas = dfa['Fecha/Hora'].dt.date.unique().tolist()
        lotes_unicos = temp_df['Lote'].unique().tolist()
        turnos_unicos = temp_df['Turno'].unique().tolist()
        valvulas_unicas = temp_df['Valvula'].unique().tolist()

        # Crear gráfico si hay datos después de filtrar
        graph_html_puntos = None
        if not temp_df.empty:
            puntos = temp_df[['Fecha/Hora', 'Lote', 'Turno', 'Valvula', 'CE_suelo', 'PH_suelo']]
            fig = px.scatter(
                puntos,
                x='CE_suelo',
                y='PH_suelo',
                color='Lote',
                size='CE_suelo',
                hover_data=['Fecha/Hora', 'Lote', 'Turno', 'Valvula'],
                title='Relación CE del Suelo vs PH del Suelo',
                labels={'CE_suelo': 'CE ms/cm', 'PH_suelo': 'PH'},
                template='plotly_white',
                size_max=20
            )

            fig.update_layout(
                title_font=dict(size=24, family='Arial', color='darkblue'),
                xaxis=dict(
                    title='CE del Suelo (mS/cm)',
                    showgrid=True,
                    gridcolor='lightgray',
                    zeroline=False,
                    title_font=dict(size=18)
                ),
                yaxis=dict(
                    title='PH del Suelo',
                    showgrid=True,
                    gridcolor='lightgray',
                    zeroline=False,
                    title_font=dict(size=18)
                ),
                legend=dict(
                    title='Lote',
                    font=dict(size=14),
                    bgcolor='rgba(255, 255, 255, 0.8)',
                    bordercolor='gray',
                    borderwidth=1
                ),
                plot_bgcolor='rgba(240, 240, 240, 0.8)'
            )

            graph_html_puntos = fig.to_html(full_html=False)

    except Exception as e:
        return render_template('ficha.html', message=f"Error: {str(e)}")
    



    ###########################
    # Mapa con Folium
    df_filtered = df[['Fecha/Hora', 'Latitud', 'Longitud', 'Lote', 'CE_suelo', 'PH_suelo', 'Valvula']].dropna()

    # Obtener fecha seleccionada para el mapa
    selected_date = request.args.get('date')
    fechas_disponibles = df_filtered['Fecha/Hora'].dt.date.unique().tolist()

    if selected_date:
        df_filtered = df_filtered[df_filtered['Fecha/Hora'].dt.date == pd.to_datetime(selected_date).date()]

    # Crear el mapa con Folium
    center_lat, center_lon = 13.4893127, -87.0525313
    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=14)

    # Cambiar el mapa base a Esri Satellite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='&copy; <a href="https://www.esri.com/">Esri</a>',
        name='Esri Satellite', overlay=True, control=True
    ).add_to(folium_map)

    # Agregar marcadores al mapa
    marker_cluster = MarkerCluster(disableClusteringAtZoom=16).add_to(folium_map)
    for _, row in df_filtered.iterrows():
        info_text = (
            f"Lote: {row['Lote']}<br>"
            f"Fecha/Hora: {row['Fecha/Hora']}<br>"
            f"CE ms Suelo: {row['CE_suelo']}<br>"
            f"PH Suelo: {row['PH_suelo']}<br>"
            f"Valvula: {row['Valvula']}"
        )
        folium.Marker(
            location=[row['Latitud'], row['Longitud']],
            tooltip=info_text,
            icon=folium.Icon(color='black', icon_color='yellow', icon='info-sign', prefix='glyphicon')
        ).add_to(marker_cluster)

    # Renderizar los gráficos y el mapa
    graph_html_lineas = pio.to_html(fig_lineas, full_html=False)
    folium_map_html = folium_map._repr_html_()

    return render_template(
        'ficha.html',
        data=data,
        graph_html_lineas=graph_html_lineas,
        folium_map_html=folium_map_html,
        graph_html_puntos=graph_html_puntos,
        lotes=lotes,
        selected_lote=selected_lote,
        selected_date=selected_date,
        fechas_disponibles=fechas_disponibles,
        fechas_unicas=fechas_unicas,
        lotes_unicos=lotes_unicos,
        turnos_unicos=turnos_unicos,
        valvulas_unicas=valvulas_unicas,
        # Otros parámetros si son necesarios
    )



@app.route('/reset', methods=['GET'])
def reset():
    return ficha()


@app.route('/estimaciones')
def estimaciones():
    collection = db['estimaciones_data']
    data = list(collection.find())
    df = pd.DataFrame(data)

    registros = df.to_dict(orient='records')

    return render_template('estimaciones.html', data=data)



@app.route('/pulverizacion')
def pulverizacion():
    collection = db['pulverizaciones_data']
    data = list(collection.find())
    df = pd.DataFrame(data)
    registros = df.to_dict(orient='records')
    return render_template('pulverizacion.html', data=data)

@app.route('/ingreso')
def ingreso():
    return render_template('ingreso.html')

if __name__ == "__main__":
    app.run(debug=True)


###grafico para tensiometro y=sensor x=fecha , desplegar por lote ver los 
##2 sensores de 24 y 12.
##agregar en estimacinoes curva de creimiento items como pega 1 y pega 2 
#numero de melon para la curva de crecimliento
#humedad relativa en
#que colocar que el area de personal que sea editable
