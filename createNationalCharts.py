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

# Funzione lambda per l'estrazione, la costruzione dei grafici e il deployment delle pagine web su S3
def lambda_handler(event, context):
	## Estraggo i dati dalla sorgente
	data_reg = take_data()
	## Costruzione della pagina html con i grafici nazionali
	create_charts(data_reg)
	## Interazione con s3 per il salvataggio delle pagine aggiornate
	insert_in_s3()

	return {
        'statusCode': 200,
        'body': 'Saved'
    }

def insert_inside(outputfile, filename, rel_path=''):
	# Inserimento del grafico all'interno della pagina generale
    print(f'<iframe src="{rel_path}{filename}" width="100%" sandbox="allow-same-origin allow-scripts" height="470" scrolling="no" seamless="seamless" frameborder="0"></iframe>', file=outputfile)
    print('<br>', file=outputfile)
    print(f'<a href="{rel_path}{filename}">Schermo intero</a>', file=outputfile)
    print('<br>', file=outputfile)

def take_data():
	data_reg = pd.read_csv(variables.PATH_CSV)
	data_reg['data'] = data_reg['data'].apply(lambda x: x[:10]) # Imposto la colonna delle date in un formato leggibile
	return data_reg

def create_charts(data_reg):
	with open('/tmp/'+variables.html_files[0], mode='wt', encoding='utf-8') as italiafile:
	    print(variables.header, file=italiafile)
	    print('<a href="../index.html">Torna alla Home</a><br><h1>Grafici nazionali</h1><br><hr><br>', file=italiafile)
	    print('', file=italiafile)

	    # Modificare qui se si vuole graficare valori alternativi di interesse
	    plottable_values = ['terapia_intensiva', 'ricoverati_con_sintomi', 'isolamento_domiciliare', 'dimessi_guariti', 'deceduti', 'nuovi_positivi', 'tamponi']
	    list_to_plot = ['terapia_intensiva', 'ricoverati_con_sintomi', 'isolamento_domiciliare', 'nuovi_positivi']
	    list_to_legend = ['Terapia intensiva', 'Ricoverati con sintomi', 'Isolamento domiciliare', 'Nuovi positivi']
	    list_to_daily_plot = ['deceduti', 'dimessi_guariti']
	    list_to_daily_legend = ['Deceduti', 'Dimessi guariti']

		## Costruzione grafico "Cumulativo" ##
	    print('<h3>Cumulativo</h3>', file=italiafile)

	    filename = f'/tmp/'+ variables.html_files[1]
	    insert_inside(italiafile, variables.html_files[1], '../grafici/')	#posizione dei grafici -> grafici/totali.html
	    output_file(filename)
	    
	    # Preparazione layout del grafico indicando il tipo di dato su ascisse e ordinata
	    p = figure(width=880, height=450, x_axis_type='datetime', sizing_mode='stretch_both', y_range=DataRange1d(only_visible=True))
	    p.tools.append(HoverTool(tooltips=[("Tipo", "$name"), ('Data', '@date{%F}'), ("Valore", "@$name")], formatters={'@date': 'datetime'}))

	    # Creazione di una tabella pivot per la gestione dei soli valori di interesse, organizzata giorno per giorno sulle righe e
	    # lista dei valori voluti sulle colonne, inoltre effettua la somma dei valori con stessa data sommando quindi i valori delle varie regioni ottenendo il valore nazionale
	    sum_field = data_reg.pivot_table(index=['data'], values=plottable_values, aggfunc='sum')
	    
	    # Oggetto che consente successivamente l'aggiunta dei valori sul grafico
	    ds = ColumnDataSource()
	    ds.data['date'] = pd.to_datetime(sum_field.index)
	    for value in plottable_values:
	        ds.data[value] = sum_field[value]

	    # Costruzione effettiva del grafico in base ai valori presenti nel datasource
	    p.varea_stack(stackers=list_to_plot, legend_label=list_to_legend, x='date', color=Category10_10[:len(list_to_plot)], source=ds)
	    p.vline_stack(stackers=list_to_plot, legend_label=list_to_legend, x='date', color=Category10_10[:len(list_to_plot)], source=ds)
	    p.legend.items.reverse()
	    p.title.text = f'Casi in Italia (cumulativo)'
	    p.legend.location = 'top_right'
	    p.legend.click_policy = 'hide'
	    p.yaxis.formatter = NumeralTickFormatter(format='0')
	    p.xaxis.formatter = DatetimeTickFormatter()
	    p.xaxis.ticker.desired_num_ticks = 20

	    save(p)

		## Costruzione grafico "Giornaliero" ##
	    print('<br><hr><br><h3>Giornaliero</h3>', file=italiafile)

	    filename = f'/tmp/'+variables.html_files[2]
	    insert_inside(italiafile, variables.html_files[2], '../grafici/')
	    output_file(filename)
	    
	    p = figure(width=880, height=450, x_axis_type='datetime', sizing_mode='stretch_both', y_range=DataRange1d(only_visible=True))
	    p.tools.append(HoverTool(tooltips=[("Tipo", "$name"), ('Data', '@date{%F}'), ("Valore", "@$name")], formatters={'@date': 'datetime'}))

	    # Per il calcolo giornaliero sottraggo i valori del giorno precedente
	    daily = sum_field[1:] - sum_field.values[:-1]
	    daily[daily[list_to_daily_plot] < 0] = 0

	    ds = ColumnDataSource()
	    ds.data['date'] = pd.to_datetime(daily.index)
	    for value in plottable_values:
	        ds.data[value] = daily[value]
	    sum_field[sum_field['nuovi_positivi'] < 0] = 0	# falsi positivi
	    ds.data['nuovi_positivi'] = sum_field['nuovi_positivi'][1:]

	    p.vbar(top='nuovi_positivi', x='date', source=ds, width=datetime.timedelta(days=1) * .8, color=Category10_10[len(list_to_daily_plot):][3], legend_label='Nuovi positivi',
	           name='nuovi_positivi')
	    legend_entry = p.legend.items.pop()
	    p.vbar_stack(stackers=list_to_daily_plot, width=datetime.timedelta(days=1) * .8, legend_label=list_to_daily_legend, x='date', color=Category10_10[:len(list_to_daily_plot)], source=ds)
	    p.legend.items.reverse()
	    p.legend.items.insert(0, legend_entry)
	    p.title.text = f'Casi in Italia (giornaliero)'
	    p.legend.location = 'top_right'
	    p.legend.click_policy = 'hide'
	    p.yaxis.formatter = NumeralTickFormatter(format='0')
	    p.xaxis.formatter = DatetimeTickFormatter()
	    p.xaxis.ticker.desired_num_ticks = 20

	    save(p)

		## Costruzione grafico "Tamponi" ##
	    print('<br><hr><br><h3>Tamponi (giornaliero)</h3>', file=italiafile)

	    filename = f'/tmp/'+variables.html_files[3]
	    insert_inside(italiafile, variables.html_files[3], '../grafici/')
	    output_file(filename)

	    p = figure(width=880, height=450, x_axis_type='datetime', sizing_mode='stretch_both', y_range=DataRange1d(only_visible=True))
	    p.tools.append(HoverTool(tooltips=[('Date', '@date{%F}'), ("Value", "@value")], formatters={'@date': 'datetime'}))

	    ds = ColumnDataSource()
	    # calcolo giornaliero sui tamponi
	    daily_tam = sum_field['tamponi'][1:] - sum_field['tamponi'].values[:-1]
	    ds.data['value'] = daily_tam.values
	    ds.data['date'] = pd.to_datetime(daily_tam.index)
	    p.vbar(source=ds, x='date', top='value', name="Tamponi giornaliero", color=Category10_10[0], width=datetime.timedelta(days=1) * .8, legend_label="Tamponi (giornaliero)")

	    p.title.text = f'Tamponi (giornaliero)'
	    p.legend.location = 'top_left'
	    p.yaxis.formatter = NumeralTickFormatter(format='0')
	    p.xaxis.formatter = DatetimeTickFormatter()
	    p.xaxis.ticker.desired_num_ticks = 20

	    save(p)

	## Footer pagina HTML
	    print('<br><hr><br>', file=italiafile)
	    print(variables.footer, file=italiafile)

def insert_in_s3():
	# Salvataggio delle pagine su S3
	s3 = boto3.resource("s3")
	for i in range(0, len(variables.html_files)):
		lambda_path = "/tmp/" + variables.html_files[i]
		if(i == 0):
			path_to_put = "risorse/"
		else:
			path_to_put = "grafici/"
		obj = s3.Object(variables.BUCKET_NAME, path_to_put + variables.html_files[i])
		obj.delete()	# per cancellare una vecchia pagina non aggiornata
		with open(lambda_path, mode='r', encoding='utf-8') as file:
			binary_file = file.read()
			print (f"[INFO] Saving Data to S3 {variables.BUCKET_NAME} Bucket...")
			s3.Bucket(variables.BUCKET_NAME).put_object(Body=binary_file, Bucket=variables.BUCKET_NAME, Key=path_to_put+variables.html_files[i], ContentType='text/html')
