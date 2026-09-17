import re
import os
import json
import random
import sqlite3
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=".")
CORS(app)

DB_NAME = "leads.db"

# ====================================================================
# BANCO DE DADOS LOCAL
# ====================================================================

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

# ====================================================================
# GERADOR DE LEADS COM TRATAMENTO ESTRITO DE NÚMERO
# ====================================================================

def buscar_e_gerar_leads(nicho, cidade):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    prefixos = ["Studio", "Espaço", "Centro de Beleza", "Barbearia", "Clínica", "Ateliê", "Concept", "Grupo"]
    sobrenomes = ["VIP", "Elegance", "Prime", "Imperial", "Central", "Master", "Luxo", "Style"]

    ddd = "21" if "rio" in cidade.lower() or "rj" in cidade.lower() else "11"

    for i in range(1, 9):
        nome_empresa = f"{random.choice(prefixos)} {random.choice(sobrenomes)} - {nicho}"
        
        # Gerando partes numéricas
        parte1 = random.randint(6000, 9999)
        parte2 = random.randint(1000, 9999)
        
        # Telefone formatado para exibição visual
        telefone = f"({ddd}) 9{parte1}-{parte2}"
        
        # OBRIGATÓRIO: Apenas dígitos (Sem -, sem (), sem espaços)
        clean_phone = f"55{ddd}9{parte1}{parte2}"

        has_site = (i % 2 == 0)
        slug = re.sub(r'[^a-zA-Z0-9]', '', nome_empresa.lower())
        website = f"https://www.{slug}.com.br" if has_site else None
        rating = round(random.uniform(4.3, 5.0), 1)
        reviews = random.randint(12, 190)
        address = f"Av. Principal, {random.randint(100, 1500)} - {cidade}"

        cursor.execute('''
            INSERT INTO leads (name, niche, location, phone, clean_phone, website, rating, reviews, address)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome_empresa, nicho, cidade, telefone, clean_phone, website, rating, reviews, address))

    conn.commit()
    conn.close()

# ====================================================================
# AGENTE DE IA & GERADOR DE COPY
# ====================================================================

def aplicar_spintax(texto):
    padrao = re.compile(r'\{([^{}]+)\}')
    while padrao.search(texto):
        texto = padrao.sub(lambda m: random.choice(m.group(1).split('|')), texto)
    return texto

def gerar_pitch_com_ia(nome, nicho, cidade="", possui_site=False, nota="", avaliacoes="", objetivo="diagnostico", api_key=None):
    if isinstance(possui_site, str):
        possui_site_bool = possui_site.lower() in ['true', '1', 'sim']
    else:
        possui_site_bool = bool(possui_site)

    if api_key and api_key.strip():
        try:
            prompt = f"""Você é um especialista em conversão web. Escreva uma mensagem curta de WhatsApp.
EMPRESA: {nome} | NICHO: {nicho} | POSSUI SITE: {'SIM' if possui_site_bool else 'NÃO'}
REGRAS:
1. NÃO mencione cidade, nota do Google ou quantidade de avaliações.
2. NÃO ofereça demonstração ou modelo.
3. Foque na perda de clientes por falta de site ou lentidão mobile.
4. Termine perguntando se a pessoa tem interesse no serviço de melhoria do site.
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
            headers = {'Content-Type': 'application/json'}
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception:
            pass

    saudacao = "{Olá|Opa|Tudo bem|Oi, tudo joia}"
    if possui_site_bool:
        corpo = f"{{Dei uma olhada na versão mobile do site da {nome} e percebi que a navegação pode ser otimizada para capturar mais contatos.}}"
        cta = "{Você teria interesse no serviço de melhoria e otimização para o site de vocês?}"
    else:
        corpo = f"{{Estava analisando empresas do nicho de {nicho} e notei que a {nome} ainda não possui um site otimizado para o celular.}}"
        cta = "{Você teria interesse no serviço de criação de site profissional para atração de novos contatos?}"

    return aplicar_spintax(f"{saudacao}!\n\n{corpo}\n\n{cta}")

# ====================================================================
# ROTAS FLASK
# ====================================================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/buscar', methods=['POST'])
def api_buscar():
    try:
        data = request.json or {}
        niche = data.get('niche', 'Barbearia e Salão de Beleza')
        location = data.get('location', 'Rio de Janeiro, RJ')

        buscar_e_gerar_leads(niche, location)

        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        leads = [dict(r) for r in rows]
        conn.close()

        return jsonify({"success": True, "leads": leads})
    except Exception as e:
        return jsonify({"success": False, "message": str(e), "leads": []}), 200

@app.route('/api/leads-tempo-real', methods=['GET'])
def api_leads_tempo_real():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    leads = [dict(r) for r in rows]
    conn.close()
    return jsonify({"success": True, "leads": leads})

@app.route('/api/gerar-pitch-ia', methods=['POST'])
def api_gerar_pitch_ia():
    data = request.json or {}
    texto_gerado = gerar_pitch_com_ia(
        nome=data.get('name', 'Empresa Local'),
        nicho=data.get('niche', 'Empresa'),
        cidade=data.get('location', ''),
        possui_site=data.get('hasWebsite', False),
        nota=data.get('rating', ''),
        avaliacoes=data.get('reviews', ''),
        objetivo=data.get('objective', 'diagnostico'),
        api_key=data.get('geminiApiKey', '')
    )
    return jsonify({"success": True, "copy": texto_gerado})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
