from flask import Flask, request, jsonify
from datetime import datetime
import re
import tempfile
import os

app = Flask(__name__)

# Valores aceitos pelo sistema
VALORES_ACEITOS = [10, 20, 30, 18, 25, 15, 29, 24, 22, 200]

@app.route('/')
def home():
    return jsonify({
        "status": "online", 
        "message": "API de validacao de comprovantes para Manny Chat",
        "valores_aceitos": VALORES_ACEITOS
    })

def detectar_tipo_arquivo(arquivo):
    """Detecta se o arquivo é PDF ou imagem"""
    try:
        filename = arquivo.filename.lower()
        
        # Verificar extensões de imagem
        extensoes_imagem = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.heic', '.tiff']
        if any(filename.endswith(ext) for ext in extensoes_imagem):
            return "imagem"
        
        # Verificar se é PDF
        if filename.endswith('.pdf'):
            return "pdf"
            
        return "outro"
    except Exception:
        return "desconhecido"

def extrair_texto_pdf(file_path):
    """Extrai texto de PDF usando pdfplumber"""
    try:
        import pdfplumber
        texto = ""
        with pdfplumber.open(file_path) as pdf:
            for pagina in pdf.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina + " "
        return texto.lower()
    except Exception as e:
        print(f"Erro ao extrair texto: {e}")
        return ""

def encontrar_valor(texto):
    """Encontra valor no texto - VERSÃO MELHORADA"""
    # Primeiro: procurar por padrões específicos de valor
    padroes_prioritarios = [
        r'valor\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'total\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'r\$\s*(\d+[.,]\d{2})\s*\(valor',
        r'pagamento\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'valor\s*do\s*pagamento\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
    ]
    
    # Buscar primeiro nos padrões prioritários
    for padrao in padroes_prioritarios:
        encontrados = re.findall(padrao, texto, re.IGNORECASE)
        for valor in encontrados:
            try:
                valor_str = valor.replace(',', '.')
                valor_float = float(valor_str)
                valor_inteiro = int(valor_float)
                
                if valor_inteiro in VALORES_ACEITOS:
                    print(f"Valor PRIORITÁRIO encontrado: {valor_inteiro}")
                    return valor_inteiro
            except:
                continue
    
    # Se não encontrou nos prioritários, buscar em padrões gerais
    padroes_gerais = [
        r'r\$\s*(\d+[.,]\d{2})',
        r'(\d+[.,]\d{2})\s*reais',
        r'rs\s*(\d+[.,]\d{2})',
    ]
    
    for padrao in padroes_gerais:
        encontrados = re.findall(padrao, texto)
        for valor in encontrados:
            try:
                if isinstance(valor, tuple):
                    valor_str = valor[-1]
                else:
                    valor_str = valor
                
                valor_str = valor_str.replace(',', '.')
                valor_float = float(valor_str)
                valor_inteiro = int(valor_float)
                
                if valor_inteiro in VALORES_ACEITOS:
                    print(f"Valor GERAL encontrado: {valor_inteiro}")
                    return valor_inteiro
            except:
                continue
    
    print("Nenhum valor válido encontrado")
    return None

def encontrar_data(texto):
    """Encontra data no texto - PORTUGUÊS e INGLÊS"""
    meses = {
        # Português
        'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12,
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4, 'maio': 5, 'junho': 6,
        'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
        # Inglês
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
    }
    
    padroes = [
        # Formato "17 OUT 2025" ou "17 OCT 2025"
        r'(\d{1,2})\s*(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})',
        # Formatos numéricos
        r'(\d{1,2})/(\d{1,2})/(\d{4})',
        r'(\d{1,2})-(\d{1,2})-(\d{4})',
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{1,2})/(\d{1,2})/(\d{2})',
    ]
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto, re.IGNORECASE)
        for match in encontrados:
            try:
                if len(match) == 3:
                    dia = int(match[0])
                    mes_str = match[1].lower()
                    ano = int(match[2])
                    
                    # Se o mês for texto, converter para número
                    if mes_str in meses:
                        mes = meses[mes_str]
                    else:
                        # Tentar converter para número se for string numérica
                        mes = int(mes_str)
                    
                    # Validar se é uma data real
                    if 1 <= dia <= 31 and 1 <= mes <= 12 and 2020 <= ano <= 2030:
                        data_encontrada = datetime(ano, mes, dia).date()
                        print(f"Data detectada: {dia}/{mes}/{ano}")
                        return data_encontrada
            except Exception as e:
                print(f"Erro ao processar data {match}: {e}")
                continue
    
    print("Nenhuma data válida encontrada no texto")
    return None

@app.route('/validar', methods=['POST'])
def validar_comprovante():
    try:
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify(False), 200
        
        arquivo = request.files['file']
        
        if arquivo.filename == '':
            return jsonify(False), 200
        
        # DETECTAR TIPO DE ARQUIVO
        tipo_arquivo = detectar_tipo_arquivo(arquivo)
        
        # Se for imagem, retorna false imediatamente
        if tipo_arquivo == "imagem":
            return jsonify(False), 200
        
        # Se não for PDF, retorna false
        if tipo_arquivo != "pdf":
            return jsonify(False), 200
        
        # Salvar arquivo temporariamente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            arquivo.save(temp_file.name)
            caminho_arquivo = temp_file.name
        
        # Processar comprovante
        texto = extrair_texto_pdf(caminho_arquivo)
        valor_encontrado = encontrar_valor(texto)
        data_encontrada = encontrar_data(texto)
        data_hoje = datetime.now().date()
        
        # Limpar arquivo temporário
        try:
            os.unlink(caminho_arquivo)
        except:
            pass
        
        # DEBUG nos logs
        print(f"Valor encontrado: {valor_encontrado}")
        print(f"Data encontrada: {data_encontrada}")
        print(f"Data hoje: {data_hoje}")
        
        # VALIDAÇÕES FINAIS
        if valor_encontrado is None:
            return jsonify(False), 200
        
        if data_encontrada is None:
            return jsonify(False), 200
        
        # Verificar se é de hoje
        if data_encontrada != data_hoje:
            return jsonify(False), 200
        
        # Tudo certo - retorna o valor inteiro
        return jsonify(valor_encontrado), 200
        
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify(False), 200

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API funcionando'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"API Manny Chat rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)