import re
import json
import random
import sqlite3
import urllib.request
import urllib.parse
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

DB_NAME = "leads.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            niche TEXT,
            location TEXT,
            phone TEXT,
            clean_phone TEXT,
            website TEXT,
            rating REAL,
            reviews INTEGER,
            address TEXT,
            status TEXT DEFAULT 'novo',
            is_saved INTEGER DEFAULT 0,
            ai_diagnostic TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def buscar_google_places_real(nicho, cidade, google_api_key):
    """ Busca estabelecimentos reais no Google Maps via Google Places API """
    query = f"{nicho} em {cidade}"
    url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(query)}&key={google_api_key}&language=pt-BR"
    
    leads = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            results = data.get('results', [])

            for place in results[:12]:
                place_id = place.get('place_id')
                nome = place.get('name', 'Empresa')
                rating = place.get('rating', 4.5)
                reviews = place.get('user_ratings_total', 0)
                address = place.get('formatted_address', cidade)
                
                # Busca detalhes estendidos (Telefone e Website)
                phone, clean_phone, website = extrair_detalhes_place(place_id, google_api_key)

                leads.append({
                    "name": nome,
                    "niche": nicho,
                    "location": cidade,
                    "phone": phone,
                    "clean_phone": clean_phone,
                    "website": website,
                    "rating": rating,
                    "reviews": reviews,
                    "address": address
                })
    except Exception as e:
        print(f"⚠️ Erro na busca Places API: {e}")
        
    return leads

def extrair_detalhes_place(place_id, api_key):
    """ Traz telefone oficial e website do local """
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=formatted_phone_number,international_phone_number,website&key={api_key}"
    phone, clean_phone, website = "Não informado", "", None
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8')).get('result', {})
            phone = data.get('formatted_phone_number', 'Não informado')
            raw_phone = data.get('international_phone_number') or phone
            clean_phone = re.sub(r'\D', '', raw_phone)
            if clean_phone and not clean_phone.startswith('55'):
                clean_phone = '55' + clean_phone
            website = data.get('website')
    except Exception:
        pass
    return phone, clean_phone, website

def salvar_leads_no_banco(leads):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    for item in leads:
        cursor.execute('''
            INSERT INTO leads (name, niche, location, phone, clean_phone, website, rating, reviews, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (item['name'], item['niche'], item['location'], item['phone'], item['clean_phone'], item['website'], item['rating'], item['reviews'], item['address']))
    conn.commit()
    conn.close()

@app.route('/api/buscar', methods=['POST'])
def api_buscar():
    data = request.json or {}
    niche = data.get('niche', 'Imobiliária')
    location = data.get('location', 'Rio de Janeiro, RJ')
    places_key = data.get('placesApiKey', os.environ.get('GOOGLE_PLACES_KEY', ''))

    if places_key:
        leads = buscar_google_places_real(niche, location, places_key)
        if leads:
            salvar_leads_no_banco(leads)

    # Retorna do banco
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    leads_db = [dict(r) for r in rows]
    conn.close()

    return jsonify({"success": True, "leads": leads_db})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
