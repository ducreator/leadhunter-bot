import asyncio
import re
import os
import json
import random
import sqlite3
import urllib.request
import threading
import time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.async_api import async_playwright

app = Flask(__name__, static_folder=".")
CORS(app)

DB_NAME = "leads.db"

# ====================================================================
# BANCO DE DADOS LOCAL E PERSISTÊNCIA EM TEMPO REAL
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

# Lista de Nichos de Alta Conversão sugeridos para Busca Automática
NICHOS_ALTO_VALOR = [
    "Clínica de Estética Avançada",
    "Dermatologia e Odontologia Estética",
    "Cirurgia Plástica",
    "Escritório de Advocacia",
    "Consultoria Financeira",
    "Arquitetura e Design de Interiores",
    "Energia Solar e Automação Residencial",
    "Curso Técnico e Especializações",
    "Oficina Mecânica Frotas e Linha Pesada",
    "Assistência Técnica Especializada"
]

# ====================================================================
# AGENTE DE IA & DIAGNÓSTICO DE ALTO IMPACTO (GEMINI + SPINTAX)
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
            prompt = f"""Você é um programador e especialista em otimização de conversão web (CRO).
Escreva uma mensagem de WhatsApp curta, direta e amigável para o dono da empresa.

EMPRESA:
- Nome: {nome}
- Nicho: {nicho}
- Possui site?: {'SIM (Foco em otimização da navegação mobile e velocidade de conversão do WhatsApp)' if possui_site_bool else 'NÃO (Foco em criação de site rápido para captação de clientes)'}
- Estratégia/Ângulo selecionado: {objetivo}

REGRAS OBRIGATÓRIAS DE ABORDAGEM:
1. NÃO mencione localização/cidade, nota do Google ou quantidade de avaliações.
2. NÃO mencione que fez demonstração, modelo ou protótipo, e NÃO pergunte se ele quer ver uma demonstração.
3. Cite apenas o impacto de navegação mobile lenta ou falta de site (atrasos no carregamento fazem clientes desistirem antes de chamar).
4. Termine perguntando diretamente se a pessoa tem interesse no serviço de melhoria/otimização do site de vocês.
5. Retorne APENAS o texto final da mensagem, sem títulos e sem aspas.
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.85, "topP": 0.95}
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            print(f"⚠️ Erro no Gemini ({e}). Usando gerador de contingência...")

    # Fallback Spintax Inteligente (Sem nota, cidade ou menção a demonstração)
    saudacao = "{Olá|Opa|Tudo bem|Oi, tudo joia}"
    if possui_site_bool:
        corpo = (
            f"{{Dei uma olhada na versão mobile do site da {nome} e percebi que a navegação pode ser otimizada para capturar mais contatos.|"
            f"Analisei o site da {nome} pelo celular e notei gargalos que podem estar fazendo vocês perderem clientes para concorrentes.}} "
            "{{A cada segundo de atraso no carregamento, cerca de 20% das pessoas desistem antes de chamar.|Isso reduz significativamente a quantidade de contatos recebidos diariamente.}}"
        )
        cta = "{Você teria interesse no serviço de melhoria e otimização para o site de vocês?|Teria interesse em conhecer nosso serviço de melhoria do site para converter mais visitantes em clientes?}"
    else:
        corpo = (
            f"{{Estava analisando empresas do nicho de {nicho} e notei que a {nome} ainda não possui um site otimizado para o celular.|"
            f"Percebi que a {nome} ainda não conta com um site oficial focado em capturar novos clientes vindos da internet.}}"
        )
        cta = "{Você teria interesse no serviço de criação e melhoria de site profissional para atração de novos contatos?|Teria interesse em entender como nosso serviço de desenvolvimento de sites pode aumentar suas vendas?}"

    return aplicar_spintax(f"{saudacao}!\n\n{corpo}\n\n{cta}")


# ====================================================================
# SCRAPER EM TEMPO REAL (GOOGLE MAPS COM TRATAMENTO SEGURO)
# ====================================================================

async def extrair_e_salvar_leads(termo_busca, max_resultados=12):
    print(f"\n🔎 [BUSCA EM TEMPO REAL] Raspando Google Maps: '{termo_busca}'...")
    leads_encontrados = []

    nicho_limpo = termo_busca.split(" em ")[0] if " em " in termo_busca else "Geral"
    cidade_limpa = termo_busca.split(" em ")[1] if " em " in termo_busca else "Brasil"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                locale="pt-BR"
            )
            page = await context.new_page()
            url_maps = f"https://www.google.com/maps/search/{termo_busca.replace(' ', '+')}"

            try:
                await page.goto(url_maps, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2500)

                feed_selector = 'div[role="feed"]'
                try:
                    await page.wait_for_selector(feed_selector, timeout=8000)
                    for _ in range(max_resultados // 2):
                        await page.eval_on_selector(feed_selector, "el => el.scrollBy(0, 1200)")
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                elementos = await page.query_selector_all('a[href*="/maps/place/"]')
                links_unicos = []
                for elem in elementos:
                    href = await elem.get_attribute('href')
                    if href and href not in links_unicos:
                        links_unicos.append(href)
                    if len(links_unicos) >= max_resultados:
                        break

                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()

                for index, link in enumerate(links_unicos, start=1):
                    try:
                        await page.goto(link, wait_until="domcontentloaded", timeout=12000)
                        await page.wait_for_timeout(800)

                        nome_elem = await page.query_selector('h1')
                        nome = await nome_elem.inner_text() if nome_elem else "Empresa sem nome"

                        rating_elem = await page.query_selector('div.F7L3fd span[aria-hidden="true"], span.ceRMgd')
                        nota = rating_elem.inner_text().replace(',', '.').strip() if rating_elem else "4.5"

                        rev_elem = await page.query_selector('button[jsaction*="moreReviews"] span, span[aria-label*="avaliações"]')
                        avaliacoes = re.sub(r'\D', '', await rev_elem.inner_text()) if rev_elem else "10"

                        phone_btn = await page.query_selector('button[data-tooltip*="telefone"], button[aria-label*="Telefone"], button[data-item-id*="phone"]')
                        telefone = "Não informado"
                        clean_phone = ""
                        if phone_btn:
                            aria_label = await phone_btn.get_attribute('aria-label')
                            if aria_label:
                                match = re.search(r'[\d\(\)\-\s\+]{8,}', aria_label)
                                if match:
                                    telefone = match.group(0).strip()
                                    clean_digits = re.sub(r'\D', '', telefone)
                                    if len(clean_digits) >= 8:
                                        clean_phone = "55" + clean_digits if not clean_digits.startswith("55") else clean_digits

                        site_btn = await page.query_selector('a[data-tooltip*="website"], a[aria-label*="website"], a[data-item-id="authority"]')
                        website = await site_btn.get_attribute('href') if site_btn else None

                        end_btn = await page.query_selector('button[data-item-id="address"]')
                        endereco = (await end_btn.get_attribute('aria-label')).replace("Endereço: ", "").strip() if end_btn else cidade_limpa

                        cursor.execute('''
                            INSERT INTO leads (name, niche, location, phone, clean_phone, website, rating, reviews, address)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (nome.strip(), nicho_limpo, cidade_limpa, telefone, clean_phone, website, float(nota) if nota.replace('.','',1).isdigit() else 4.5, int(avaliacoes) if avaliacoes.isdigit() else 0, endereco))

                        conn.commit()

                    except Exception as e:
                        print(f"⚠️ Erro ao processar item {index}: {e}")
                        continue

                conn.close()

            except Exception as e:
                print(f"❌ Erro na navegação do Maps: {e}")

            await browser.close()
    except Exception as err:
        print(f"❌ Erro ao inicializar o Playwright: {err}")


# ====================================================================
# ROTAS FLASK
# ====================================================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/buscar', methods=['POST'])
def api_buscar():
    data = request.json or {}
    niche = data.get('niche', 'Clínica de Estética Avançada')
    location = data.get('location', 'Rio de Janeiro, RJ')
    termo = f"{niche} em {location}"

    try:
        # Executa o scraper Playwright de forma tratada para não dar Crash 500
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(extrair_e_salvar_leads(termo, max_resultados=10))
            loop.close()
        except Exception as scrape_err:
            print(f"⚠️ Falha na execução do Playwright: {scrape_err}")

        # Retorna os leads do SQLite de forma garantida
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        leads = [dict(r) for r in rows]
        conn.close()

        return jsonify({"success": True, "leads": leads, "source": "real_database"})
    except Exception as e:
        print(f"❌ Erro na rota /api/buscar: {e}")
        return jsonify({"success": False, "message": str(e), "leads": []}), 200

@app.route('/api/leads-tempo-real', methods=['GET'])
def api_leads_tempo_real():
    """ Rota de Polling Automático """
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
    print("=" * 60)
    print("🚀 LEADHUNTER PRO - COM BANCO DE DADOS EM TEMPO REAL & NOVO MOTOR IA")
    print("📱 Acesse no seu navegador: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
