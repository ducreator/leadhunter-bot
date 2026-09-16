import asyncio
import re
import os
import json
import random
import urllib.request
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from playwright.async_api import async_playwright

app = Flask(__name__, static_folder=".")
CORS(app)

# ====================================================================
# AGENTE DE IA & MOTOR SPINTAX ANTI-BAN DO WHATSAPP
# ====================================================================

def aplicar_spintax(texto):
    """ Processa padrões do tipo {opção1|opção2|opção3} para gerar variações ilimitadas """
    padrao = re.compile(r'\{([^{}]+)\}')
    while padrao.search(texto):
        texto = padrao.sub(lambda m: random.choice(m.group(1).split('|')), texto)
    return texto

def gerar_pitch_com_ia(nome, nicho, cidade, possui_site, nota, avaliacoes, objetivo="redesign", api_key=None):
    """
    Gera abordagens 100% inéditas para evitar bloqueios no WhatsApp.
    Mapeia perfil de Programador de Sites focando em envio de portfólio.
    """
    if isinstance(possui_site, str):
        possui_site_bool = possui_site.lower() in ['true', '1', 'sim']
    else:
        possui_site_bool = bool(possui_site)

    # 1. TENTATIVA COM GEMINI (IA COMPLETA COM ROTAÇÃO SINTÁTICA EXTREMA)
    if api_key and api_key.strip():
        try:
            prompt = f"""Você é um programador de sites e desenvolvedor web freelancer.
Escreva uma mensagem de abordagem para o WhatsApp para o dono do estabelecimento abaixo.

DADOS DA EMPRESA:
- Nome: {nome}
- Nicho: {nicho}
- Cidade: {cidade}
- Possui site?: {'SIM (Foco em modernizar layout/mobile)' if possui_site_bool else 'NÃO (Foco em criar site do zero)'}
- Avaliação Google: {nota} estrelas ({avaliacoes} avaliações)
- Ângulo selecionado: {objetivo}

DIRETRIZES DE SEGURANÇA ANTI-BAN WHATSAPP (MUITO IMPORTANTE):
1. Crie uma mensagem TOTALMENTE INÉDITA, natural, curta (3 a 5 linhas).
2. NUNCA use padrões engessados de vendas. Escreva como um desenvolvedor real trocando uma ideia rápida.
3. Se tiver site: Diga que é programador e viu o perfil deles no Google, deu uma olhada no site pelo celular e notou que dá pra deixar o design bem mais moderno e focado em gerar chamadas no WhatsApp.
4. Se NÃO tiver site: Diga que é programador de sites, viu as ótimas avaliações deles no Google e percebeu que ainda não têm um site oficial para converter visitantes em clientes em {cidade}.
5. PERGUNTA FINAL (OBRIGATÓRIA): Ofereça enviar 2 ou 3 links de exemplos do seu portfólio/projetos recentes pelo WhatsApp sem compromisso.
6. Não prometa reuniões longas, auditorias em vídeo ou relatórios extensos.
7. Varie os sinônimos, saudações e estilo para garantir que a mensagem seja 100% única no mundo.
8. Retorne APENAS o texto final da mensagem, sem títulos, sem aspas e sem explicações.
"""
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key.strip()}"
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.9, # Alta temperatura para máxima variação das palavras
                    "topP": 0.95
                }
            }
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                texto_ia = result['candidates'][0]['content']['parts'][0]['text']
                return texto_ia.strip()
        except Exception as e:
            print(f"⚠️ Falha na API Gemini ({e}). Utilizando Motor Spintax de Alta Variação...")

    # 2. MOTOR SPINTAX LOCAL (MILHARES DE COMBINAÇÕES SEM PRECISAR DE IA PAGA)
    spintax_saudacao = "{Opa|Olá|Oi|Fala pessoal|Tudo bem|Como vai},{ tudo certo|tudo joia|tudo tranquilo}?"
    
    spintax_intro = "{Sou desenvolvedor web|Sou programador de sites|Trabalho desenvolvendo sites|Sou dev front-end|Faço criação e modernização de sites}."

    if possui_site_bool:
        spintax_corpo = (
            "{{Estava navegando no Google Maps e|Estava pesquisando sobre|Estava buscando empresas de}} "
            f"{nicho} em {cidade} {{e vi|e encontrei}} a {{excelente|ótima}} reputação de vocês ({nota} ⭐). "
            "{{Dei uma olhada rápida no site de vocês pelo celular|Acessei o site oficial pelo telefone|Estive no site de vocês agora}} "
            "{{e notei que|percebi que}} {{dá para modernizar bastante a estrutura|dá para dar um upgrade no visual|a página pode ser otimizada}} "
            "{{para carregar mais rápido no celular e gerar mais contatos no WhatsApp|para converter mais visitantes em clientes diários|para ficar muito mais atraente no mobile}}."
        )
        spintax_cta = (
            "{Posso te mandar aqui 2 ou 3 exemplos de sites modernos que criei para você ver o estilo sem compromisso?|"
            "Se fizer sentido, posso te enviar meu portfólio com alguns modelos recentes para você dar uma olhada?|"
            "Quer que eu te mande no Whats alguns projetos que fiz para o seu segmento só para você comparar o layout?|"
            "Posso te mandar 2 links de projetos parecidos que desenvolvi para você ver como ficaria o visual?}"
        )
    else:
        spintax_corpo = (
            "{{Estava pesquisando no Google por|Estava buscando referências de|Encontrei o perfil de vocês em}} "
            f"{nicho} em {cidade} {{e notei|e vi}} que vocês têm {avaliacoes} avaliações {{super positivas|muito boas}}. "
            "{{Porém, percebi que vocês ainda não possuem um site oficial cadastrado|Porém, notei que estão sem uma página própria na internet|Porém, vi que não há link de site no perfil}}. "
            f"{{Hoje em dia muitos clientes em {cidade} acabam optando por concorrentes que têm site rápido no celular|Hoje em dia ter uma página moderna transmite muito mais autoridade e fecha contratos mais rápido}}."
        )
        spintax_cta = (
            "{Posso te mandar 2 ou 3 modelos de sites que desenvolvi para você ver como ficaria a página de vocês?|"
            "Se você quiser, posso te enviar no WhatsApp 2 exemplos do meu portfólio para você ver a estrutura sem compromisso?|"
            "Quer que eu te mande alguns exemplos rápidos de sites que criei para este nicho só para você conhecer meu trabalho?}"
        )

    template_final = f"{spintax_saudacao} {spintax_intro}\n\n{spintax_corpo}\n\n{spintax_cta}"
    return aplicar_spintax(template_final)


# ====================================================================
# RASPAGEM DO GOOGLE MAPS EM TEMPO REAL
# ====================================================================

async def extrair_leads_google_maps(termo_busca, max_resultados=10):
    print(f"\n🔎 Realizando busca no Google Maps: '{termo_busca}'...")
    leads = []

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
            await page.wait_for_timeout(3000)

            feed_selector = 'div[role="feed"]'
            
            try:
                await page.wait_for_selector(feed_selector, timeout=10000)
                for _ in range(max_resultados // 2):
                    await page.eval_on_selector(feed_selector, "el => el.scrollBy(0, 1000)")
                    await page.wait_for_timeout(1200)
            except Exception as e:
                print(f"⚠️ AVISO: Feed não rolou completamente: {e}")

            elementos = await page.query_selector_all('a[href*="/maps/place/"]')
            links_unicos = []
            for elem in elementos:
                href = await elem.get_attribute('href')
                if href and href not in links_unicos:
                    links_unicos.append(href)
                if len(links_unicos) >= max_resultados:
                    break

            print(f"🎯 {len(links_unicos)} estabelecimentos encontrados. Processando detalhes...")

            for index, link in enumerate(links_unicos, start=1):
                try:
                    await page.goto(link, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(1200)

                    nome = "Empresa sem Nome"
                    h1_elem = await page.query_selector('h1')
                    if h1_elem:
                        nome = await h1_elem.inner_text()

                    nota = "4.0"
                    rating_elem = await page.query_selector('div.F7L3fd span[aria-hidden="true"], span.ceRMgd')
                    if rating_elem:
                        nota_text = await rating_elem.inner_text()
                        nota = nota_text.replace(',', '.').strip()

                    avaliacoes = "0"
                    rev_elem = await page.query_selector('button[jsaction*="moreReviews"] span, span[aria-label*="avaliações"]')
                    if rev_elem:
                        rev_text = await rev_elem.inner_text()
                        avaliacoes = re.sub(r'\D', '', rev_text) or "0"

                    telefone = "Não informado"
                    phone_btn = await page.query_selector('button[data-tooltip*="telefone"], button[aria-label*="Telefone"], button[data-item-id*="phone"]')
                    if phone_btn:
                        aria_label = await phone_btn.get_attribute('aria-label')
                        if aria_label:
                            tel_match = re.search(r'[\d\(\)\-\s\+]{8,}', aria_label)
                            if tel_match:
                                telefone = tel_match.group(0).strip()

                    website = None
                    site_btn = await page.query_selector('a[data-tooltip*="website"], a[aria-label*="website"], a[data-item-id="authority"]')
                    if site_btn:
                        website = await site_btn.get_attribute('href')

                    endereco = "Endereço não informado"
                    end_btn = await page.query_selector('button[data-item-id="address"]')
                    if end_btn:
                        aria_end = await end_btn.get_attribute('aria-label')
                        if aria_end:
                            endereco = aria_end.replace("Endereço: ", "").strip()

                    clean_phone = "55" + re.sub(r'\D', '', telefone) if telefone != "Não informado" else ""

                    leads.append({
                        "id": index,
                        "name": nome.strip(),
                        "niche": termo_busca.split(" em ")[0] if " em " in termo_busca else "Empresa Local",
                        "phone": telefone,
                        "cleanPhone": clean_phone,
                        "website": website,
                        "rating": float(nota) if nota.replace('.', '', 1).isdigit() else 4.0,
                        "reviews": int(avaliacoes) if avaliacoes.isdigit() else 0,
                        "address": endereco,
                        "status": "novo",
                        "isSaved": False
                    })

                    print(f" [{index}/{len(links_unicos)}] {nome} | Tel: {telefone} | Site: {'Sim' if website else 'Não ⚠️'}")

                except Exception as e:
                    print(f" ⚠️ Erro no item {index}: {e}")
                    continue

        except Exception as e:
            print(f" ❌ Erro na raspagem: {e}")

        await browser.close()

    return leads


# ====================================================================
# ROTAS FLASK
# ====================================================================

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/buscar', methods=['POST'])
def api_buscar():
    data = request.json or {}
    niche = data.get('niche', 'Hamburguerias')
    location = data.get('location', 'Rio de Janeiro, RJ')
    termo = f"{niche} em {location}"

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        leads = loop.run_until_complete(extrair_leads_google_maps(termo, max_resultados=10))
        loop.close()
        
        return jsonify({"success": True, "leads": leads})
    except Exception as e:
        print(f"❌ Erro na busca: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/gerar-pitch-ia', methods=['POST'])
def api_gerar_pitch_ia():
    data = request.json or {}
    nome = data.get('name', 'Empresa Local')
    nicho = data.get('niche', 'Empresa')
    cidade = data.get('location', 'sua cidade')
    possui_site = data.get('hasWebsite', False)
    nota = data.get('rating', '4.5')
    avaliacoes = data.get('reviews', '20')
    objetivo = data.get('objective', 'redesign')
    api_key = data.get('geminiApiKey', '')

    try:
        texto_gerado = gerar_pitch_com_ia(
            nome=nome,
            nicho=nicho,
            cidade=cidade,
            possui_site=possui_site,
            nota=nota,
            avaliacoes=avaliacoes,
            objetivo=objetivo,
            api_key=api_key
        )
        return jsonify({"success": True, "copy": texto_gerado})
    except Exception as e:
        print(f"❌ Erro na IA: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 SERVIDOR COM MOTOR ANTI-BAN & AGENTE DE IA INICIADO!")
    print("📱 Acesse no seu navegador: http://localhost:5000")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)