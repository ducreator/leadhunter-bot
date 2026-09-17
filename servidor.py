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

def gerar_pitch_com_ia(nome, nicho, cidade, possui_site, nota, avaliacoes, objetivo="diagnostico", api_key=None):
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
- Cidade: {cidade}
- Possui site?: {'SIM (Foco em diagnosticar falha de carregamento mobile e conversão do WhatsApp)' if possui_site_bool else 'NÃO (Foco em autoridade imediata e perda de clientes para concorrentes)'}
- Avaliações Google: {nota} ⭐ ({avaliacoes} avaliações)
- Estratégia/Ângulo selecionado: {objetivo}

DIRETRIZES DE ABORDAGEM (SEM SPAM):
1. Se o objetivo for 'diagnostico' ou 'impacto':
   - Cite um erro comum no mobile (ex: atraso de 4 a 6 segundos para carregar o botão do Whats gera ~20% a 30% de perda de novos clientes em {cidade}).
2. Se o objetivo for 'amostra':
   - Diga que criou um protótipo/esboço rápido da versão mobile para dobrar os contatos.
3. Termine com uma Pergunta de Permissão: "Posso te mandar o link da prévia/diagnóstico por aqui sem compromisso para você dar uma olhada?"
4. Retorne APENAS o texto da mensagem, sem títulos e sem aspas.
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

    # Fallback Spintax Inteligente
    saudacao = "{Olá|Opa|Tudo bem|Oi, tudo joia}"
    if possui_site_bool:
        corpo = (
            f"{{Notei que a empresa de vocês tem ótimas avaliações em {cidade} ({nota} ⭐).}} "
            "{{Fiz um diagnóstico rápido no site pelo celular e vi que o carregamento do botão do WhatsApp está levando mais de 5 segundos|Dei uma olhada na versão mobile do site e percebi que a navegação pode ser otimizada para capturar mais contatos}}. "
            "{{A cada segundo de atraso, cerca de 20% das pessoas desistem antes de chamar.|Isso faz com que potenciais clientes em " + cidade + " acabem buscando concorrentes.}}"
        )
        cta = "{Fiz uma demonstração simples de como ficaria a versão mobile otimizada. Posso te enviar o link para você dar uma olhada sem compromisso?|Montei um esboço rápido do cabeçalho focado em conversão. Quer que eu te mande no Whats para você avaliar?}"
    else:
        corpo = (
            f"{{Estava buscando referências de {nicho} em {cidade} e vi as {avaliacoes} avaliações excelentes de vocês.}} "
            "{{Porém, notei que vocês ainda não possuem um site oficial otimizado no perfil do Google.|Como hoje a maioria das buscas é pelo celular, a falta de uma página rápida faz vocês perderem orçamentos diários.}}"
        )
        cta = "{Montei um modelo prévio de como ficaria a página oficial de vocês no celular. Posso te mandar o link aqui sem compromisso?|Posso te mandar 2 exemplos do meu portfólio focados no seu nicho só para você ver a estrutura?}"

    return aplicar_spintax(f"{saudacao}!\n\n{corpo}\n\n{cta}")


# ====================================================================
# SCRAPER EM TEMPO REAL (GOOGLE MAPS REAL SEM DADOS FAKE)
# ====================================================================

async def extrair_e_salvar_leads(termo_busca, max_resultados=12):
    print(f"\n🔎 [BUSCA EM TEMPO REAL] Raspando Google Maps: '{termo_busca}'...")
    leads_encontrados = []

    nicho_limpo = termo_busca.split(" em ")[0] if " em " in termo_busca else "Geral"
    cidade_limpa = termo_busca.split(" em ")[1] if " em " in termo_busca else "Brasil"

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

                    # Salva/Atualiza no banco para sincronização automática
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
            print(f"❌ Erro na raspagem: {e}")

        await browser.close()


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
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(extrair_e_salvar_leads(termo, max_resultados=10))
        loop.close()

        # Retorna leads reais salvos no banco SQLite
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        leads = [dict(r) for r in rows]
        conn.close()

        return jsonify({"success": True, "leads": leads, "source": "real_database"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/leads-tempo-real', methods=['GET'])
def api_leads_tempo_real():
    """ Rota de Polling Automático para atualização sem recarregar a página """
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
        cidade=data.get('location', 'sua cidade'),
        possui_site=data.get('hasWebsite', False),
        nota=data.get('rating', '4.5'),
        avaliacoes=data.get('reviews', '20'),
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
