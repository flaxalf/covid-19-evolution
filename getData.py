import variables
import json

import requests

def lambda_handler(event, context):
    # Recupero il file voluto dalla fonte, lo trasformo in un file binario per il download e lo restituisco al chiamante
    r = requests.get(variables.PATH_JSON_NAT, allow_redirects=True)
    file = r.content.decode("utf-8")
    b = bytes(file, 'utf-8')
    
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Content-Disposition": "attachment; filename=data_covid"
        },
        "body": b
    }