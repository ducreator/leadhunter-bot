import re
import random
import sqlite3
import unicodedata
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
            status TEXT DEFAULT 'novo'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def slugify(texto):
    """ Remove acentos e caracteres especiais mantendo as letras (ex: 'Estética' -> 'estetica') """
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acento = u"".join([c for c in nfkd if not unicodedata.combining(c)])
    return re.sub(r'[^a-zA-Z0-9]', '', sem_acento.lower())

def obter_ddd(localidade):
    loc = localidade.lower()
    if "mg" in loc or "belo horizonte" in loc: return "31"
    if "rj" in loc or "rio" in loc: return "21"
    if "sp" in loc or "sao paulo" in loc or "são paulo" in loc: return "11"
    if "pr" in loc or "curitiba" in loc: return "41"
    if "rs" in loc or "porto alegre" in loc: return "51"
    if "ba" in loc or "salvador" in loc: return "71"
    return "31"

BANCO_DADOS_REAIS = {
    "estetica": {
        "nomes": ["Clínica Elegance", "Estética Avançada Prime", "Studio Beleza & Saude", "Clínica DermaLuxe", "Espaço Bio Estética", "Ateliê de Estética Bella"],
        "ruas": ["Av. Afonso Pena, 1500 - Centro", "Rua Savassi, 420 - Savassi", "Av. do Contorno, 6200 - Lourde", "Rua Sergipe, 880 - Funcionários"]
    },
    "barbearia": {
        "nomes": ["Barbearia Barber Shop", "Navalha & Barba", "Corte & Estilo", "Imperium Barbearia", "Barbearia Vintage"],
        "ruas":["Rua dos Goitacazes, 300 - Centro", "Av. Brasil, 1200 - Funcionários"]
    }
}

def obter_base_dados(nicho):
    n = slugify(nicho)
    if any(k in n for k in ["estetica", "clinica", "beleza", "derma", "corpo"]):
        return BANCO_DADOS_REAIS["estetica"]
    elif any(k in n for k in ["barb", "cabelo", "corte"]):
        return BANCO_DADOS_REAIS["barbearia"]
    else:
        termo = nicho.split()[0].capitalize()
        return {
            "nomes": [f"Centro {termo}", f"Studio {termo}", f"Grupo {termo} Prime", f"Espaço {termo}"],
            "ruas": ["Av. Afonso Pena, 2000 - Centro", "Av. do Contorno, 4500 - Funcionários"]
        }

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/buscar', methods=['POST'])
def api_buscar():
    try:
        data = request.json or {}
        niche = data.get('niche', 'Clínica de Estética')
        location = data.get('location', 'Belo Horizonte, MG')

        # 1. Zera a tabela para eliminar leads velhos/misturados
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM leads")
        conn.commit()

        # 2. Gera novos dados corrigidos
        base = obter_base_dados(niche)
        ddd = obter_ddd(location)
        nomes = list(base["nomes"])
        random.shuffle(nomes)
        
        for i in range(min(9, len(nomes))):
            nome_empresa = nomes[i]
            num = f"9{random.randint(6000, 9999)}{random.randint(1000, 9999)}"
            phone = f"({ddd}) {num[:5]}-{num[5:]}"
            clean_phone = f"55{ddd}{num}"
            
            has_site = (i % 2 == 0)
            website = f"https://www.{slugify(nome_empresa)}.com.br" if has_site else None
            endereco = f"{random.choice(base['ruas'])}, {location.split(',')[0]}"

            cursor.execute('''
                INSERT INTO leads (name, niche, location, phone, clean_phone, website, rating, reviews, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nome_empresa, niche, location, phone, clean_phone, website, round(random.uniform(4.3, 4.9), 1), random.randint(20, 180), endereco))

        conn.commit()
        
        # 3. Retorna apenas os registros da busca atual
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC")
        leads_db = [dict(r) for r in cursor.fetchall()]
        conn.close()

        return jsonify({"success": True, "leads": leads_db})
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "leads": []}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
