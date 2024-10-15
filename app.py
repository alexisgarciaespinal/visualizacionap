from flask import Flask, render_template, request
import plotly.express as px
import plotly.io as pio
from pymongo import MongoClient
import numpy as np
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import logging
import json

app = Flask(__name__)

# Obtener la clave secreta desde las variables de entorno
app.secret_key = os.getenv('SECRET_KEY')

# Configurar conexión a MongoDB usando variable de entorno
mongo_uri = os.getenv('MONGO_URI')
client = MongoClient(mongo_uri)


# Configurar conexión a MongoDB
#app.secret_key = '0e01e4bcf2960bdb6aafeac4cded07b5f0bb809d8e1ff7e9'
#client = MongoClient('mongodb://localhost:27017/')
#client = MongoClient('mongodb+srv://alexisgarcia:Percha84@temporada2324.lug6z.mongodb.net/?retryWrites=true&w=majority&appName=temporada2324')
#                      mongodb+srv://alexisgarcia51:<db_password>@temporada2324.lug6z.mongodb.net/?retryWrites=true&w=majority&appName=temporada2324
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
    # Obtener todos los datos de la colección y convertirlos en un DataFrame
    data = list(collection.find())
    df = pd.DataFrame(data)

    ####################################
    # Grafico de lineas
    df_alex = df[['Fecha/Hora', 'Edad_cultivo', 
                      'Lote', 'Tensiometro_12', 'Tensiometro_24']].dropna(subset=['Tensiometro_12','Tensiometro_24'])

    lotes = df_alex['Lote'].unique()
 
    # Filtrar por lote seleccionado
    selected_lote = request.args.get('lote', default=lotes[0])  # Por defecto, selecciona el primer lote
    df_lote = df_alex[df_alex['Lote'] == selected_lote]

    # Crear una nueva columna que combine Edad_cultivo y Fecha/Hora
    df_lote['Fecha/Hora'] = pd.to_datetime(df_lote['Fecha/Hora'])
    df_lote['Edad_Hora'] = df_lote['Edad_cultivo'].astype(str) + " ddt " + df_lote['Fecha/Hora'].dt.strftime('%H:%M')

    # Crear el gráfico de líneas para los tensiómetros
    df_lineas = df_lote.melt(id_vars=['Edad_Hora', 'Lote'], 
                              value_vars=['Tensiometro_12', 'Tensiometro_24'], 
                              var_name='Tensiometro', 
                              value_name='Valor')

    fig_lineas = px.line(
        df_lineas,
        x='Edad_Hora',
        y='Valor',
        color='Tensiometro',
        title=f'Datos Tensiometros por Lote: {selected_lote}',
        labels={'Valor': 'Tensiometro', 'Edad_Hora': 'Edad del Cultivo (días y hora)'},
        markers=True
    )



    ##################################################
    # Crear el Mpa esoty usando folium
    # Reemplazar cadenas vacías por NaN
    df['Latitud'].replace('', np.nan, inplace=True)
    df['Longitud'].replace('', np.nan, inplace=True)

    # Filtrar los datos para evitar NaN pero es importante antes remplazar las celdas vacias 
    df_filtered = df[['Fecha/Hora', 'Latitud', 'Longitud', 
                      'Lote', 'CE_suelo','PH_suelo','Valvula' ]].dropna(subset=['CE_suelo', 
                                                                                  'PH_suelo',"Latitud", "Longitud"])

    # Obtener la fecha seleccionada de la solicitud
    selected_date = request.args.get('date', default=None)
    
    fechas_disponibles = pd.to_datetime(df_filtered['Fecha/Hora']).dt.date.unique().tolist()
    print(selected_date)
    if selected_date:
        # Filtrar el DataFrame por la fecha seleccionada (sin la hora)
        df_filtered['Fecha'] = pd.to_datetime(df_filtered['Fecha/Hora']).dt.date
        df_filtered = df_filtered[df_filtered['Fecha'] == pd.to_datetime(selected_date).date()]

    # Convertir Latitud y Longitud a tipo numérico
    df_filtered['Latitud'] = pd.to_numeric(df_filtered['Latitud'], errors='coerce')
    df_filtered['Longitud'] = pd.to_numeric(df_filtered['Longitud'], errors='coerce')


    center_lat = 13.4893127
    center_lon = -87.0525313
    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=14)

    # Cambiar el mapa base a Esri Satellite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='&copy; <a href="https://www.esri.com/">Esri</a>',
        name='Esri Satellite',
        overlay=True,
        control=True
    ).add_to(folium_map)

    # Agregar un MarkerCluster para los puntos
    marker_cluster = MarkerCluster(disableClusteringAtZoom=16).add_to(folium_map)
    # Agregar marcadores para cada punto en el DataFrame filtrado
    for index, row in df_filtered.iterrows():
        fecha_hora = pd.to_datetime(row['Fecha/Hora']).strftime('%Y-%m-%d %H:%M:%S')
        info_text = (
        f"Lote: {row['Lote']}<br>"
        f"Fecha/Hora: {fecha_hora}<br>"
        f"CE ms Suelo: {row['CE_suelo']}<br>"
        f"PH Suelo: {row['PH_suelo']}"
        f"Valvula: {row['Valvula']}"
    )

        folium.Marker(
            location=[row['Latitud'], row['Longitud']],
            tooltip=info_text,
            icon=folium.Icon(color='black', icon_color='yellow', icon='info-sign', prefix='glyphicon')  # Icono invisible
       ).add_to(marker_cluster)

    # Guardar el mapa como HTML
    folium_map_html = folium_map._repr_html_()

    # Guardar los gráficos como HTML
    graph_html_lineas = pio.to_html(fig_lineas, full_html=False)

    # Devolver la plantilla con los gráficos y los datos
    return render_template(
        'ficha.html',
        data=data,
        graph_html_lineas=graph_html_lineas,
        folium_map_html=folium_map_html, 
        lotes=lotes,
        selected_lote=selected_lote,
        selected_date=selected_date,
        fechas_disponibles=fechas_disponibles
    )

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
    return render_template('pulverizacion.html', data = data)


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
