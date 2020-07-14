import datetime
import boto3

import variables

import pandas as pd
from bokeh.io import save
from bokeh.palettes import Category10_10
from bokeh.plotting import figure, output_file
from bokeh.models import ColumnDataSource, NumeralTickFormatter, DatetimeTickFormatter, DataRange1d
from bokeh.models.tools import HoverTool

import json

def lambda_handler(event, context):
	# Funzione lambda per estrazione, creazione pagina html con grafici regionali e salvataggio in s3
	data_reg = take_data()
	create_regional_charts(data_reg)
	insert_in_s3()
	
	return {
        'statusCode': 200,
        'body': 'Saved',
    }


def insert_inside(outputfile, filename, rel_path=''):
	# Inserimento del grafico all'interno della pagina generale
    print(f'<iframe src="{rel_path}{filename}" width="100%" sandbox="allow-same-origin allow-scripts" height="470" scrolling="no" seamless="seamless" frameborder="0"></iframe>', file=outputfile)
    print('<br>', file=outputfile)
    print(f'<a href="{rel_path}{filename}">Schermo intero</a>', file=outputfile)
    print('<br>', file=outputfile)


def take_data():
	# Estrazione dei dati dalla fonte
	data_reg = pd.read_csv(variables.PATH_CSV)
	data_reg['data'] = data_reg['data'].apply(lambda x: x[:10])
	return data_reg

def create_regional_charts(data_reg):
	# Creazione grafici
	
	regioni = sorted(set(data_reg['denominazione_regione'])) # Ordinamento regioni, utilizzato per la stampa ordinata
	
	with open('/tmp/regionali.html', mode='wt', encoding='utf-8') as regionalifile:
		print(variables.header, file=regionalifile)
		
		# Lista dei valori graficati
		values_to_plot = ['totale_casi', 'tamponi']

		print('<a href="../index.html">Torna alla Home</a><br><h1>Confronto tra regioni</h1>', file=regionalifile)
		print('', file=regionalifile)
		## regional_html_files = ['regionali.html', 'regioni_totale.html', 'regioni_tamponi.html']
		for j, val in enumerate(values_to_plot):
			# Scrittura sul file titolo e preparazione del grafico
		    print(f'<br><hr><br><h3>{val.capitalize().replace("_", " ")}</h3>', file=regionalifile)
		    insert_inside(regionalifile, variables.regional_html_files[j+1], '../grafici/')
			
			# data_reg rappresenta la tabella con qualunque informazione presente sulla fonte
			# Attraverso la seguente tabella pivot si avrà una tabella ristrutturata
			# organizzata giorno per giorno (sulle righe), regione per regione (sulle colonne), contenente i valori indicati
		    pivot = data_reg.pivot_table(index=['data'], values=val, columns=['denominazione_regione'], aggfunc='sum')

		    filename = f'/tmp/'+ variables.regional_html_files[j+1]
		    output_file(filename)

		    # Preparazione layout del grafico (libreria bokeh)
		    p = figure(width=880, height=450, x_axis_type='datetime', sizing_mode='stretch_both', y_range=DataRange1d(only_visible=True))
		    p.tools.append(HoverTool(tooltips=[("Regione", "@regione"), ('Data', '@date{%F}'), ("Valore", "@value")], formatters={'@date': 'datetime'}))
		    
		    # Utilizzo l'oggetto datasource per poter assegnare i valori sul grafico, prelevo i dati dalla tabella pivot
		    for i, regione in enumerate(regioni):
		        ds = ColumnDataSource()
		        ds.data['value'] = pivot[regione]
		        ds.data['date'] = pd.to_datetime(pivot.index)
		        ds.data['regione'] = [regione] * len(ds.data['date'])
		        # Costruzione grafico "line" in base ai valori presenti nell'oggetto datasource
		        p.line(source=ds, x='date', y='value', name=regione, color=Category10_10[i % 10], line_width=2, legend_label=regione)
		        if i < 10:
		            p.circle(source=ds, x='date', y='value', color=Category10_10[i % 10], legend_label=regione)
		        elif i < 20:
		            p.triangle(source=ds, x='date', y='value', color=Category10_10[i % 10], legend_label=regione)
		    # Costruito il grafico aggiungo informazioni come la legenda e il titolo
		    p.title.text = f'{val.capitalize().replace("_", " ")} per regione'
		    p.legend.location = 'top_left'
		    p.legend.click_policy = 'hide'
		    p.yaxis.formatter = NumeralTickFormatter(format='0')
		    p.xaxis.formatter = DatetimeTickFormatter()
		    p.xaxis.ticker.desired_num_ticks = 20
		    p.legend.label_height = 15
		    p.legend.glyph_height = 15
		    p.legend.spacing = 0
		    save(p)
		# Footer pagina HTML, per appendere la fonte e l'ultimo aggiornamento della pagina
		print('<br><hr><br>', file=regionalifile)
		print(variables.footer, file=regionalifile)


def insert_in_s3():
	# Interazione con s3 per il salvataggio delle pagine aggiornate
	s3 = boto3.resource("s3")

	for i in range(0, len(variables.regional_html_files)):
		lambda_path = "/tmp/" + variables.regional_html_files[i]
		if(i == 0):
			path_to_put = "risorse/"
		else:
			path_to_put = "grafici/"
		obj = s3.Object(variables.BUCKET_NAME, path_to_put + variables.regional_html_files[i])
		obj.delete()	# Cancello una vecchia pagina non aggiornata
		with open(lambda_path, mode='r', encoding='utf-8') as file:
			binary_file = file.read()
			print (f"[INFO] Saving Data to S3 {variables.BUCKET_NAME} Bucket...")
			s3.Bucket(variables.BUCKET_NAME).put_object(Body=binary_file, Bucket=variables.BUCKET_NAME, Key=path_to_put+variables.regional_html_files[i], ContentType='text/html')