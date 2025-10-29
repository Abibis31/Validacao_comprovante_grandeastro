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
    """Encontra valor no texto e retorna como inteiro"""
    padroes = [
        r'r\$\s*(\d+[.,]\d{2})',
        r'valor\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'(\d+[.,]\d{2})\s*reais',
        r'rs\s*(\d+[.,]\d{2})',
        r'total\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'(\d+[.,]\d{2})',
    ]
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto)
        for valor in encontrados:
            try:
                if isinstance(valor, tuple):
                    valor_str = valor[-1]
                else:
                    valor_str = valor
                
                # Converter para float e depois para inteiro
                valor_str = valor_str.replace(',', '.')
                valor_float = float(valor_str)
                valor_inteiro = int(valor_float)
                
                # Verificar se está na lista de valores aceitos
                if valor_inteiro in VALORES_ACEITOS:
                    return valor_inteiro
                    
            except:
                continue
    return None

def encontrar_data(texto):
    """Encontra data no texto"""
    padroes = [
        r'(\d{1,2})/(\d{1,2})/(\d{4})',
        r'(\d{1,2})-(\d{1,2})-(\d{4})',
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        r'(\d{1,2})/(\d{1,2})/(\d{2})',
    ]
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto)
        for match in encontrados:
            try:
                if len(match) == 3:
                    if len(match[2]) == 2:
                        ano = int("20" + match[2])
                    else:
                        ano = int(match[2])
                    
                    dia = int(match[0])
                    mes = int(match[1])
                    
                    if 1 <= dia <= 31 and 1 <= mes <= 12 and 2020 <= ano <= 2030:
                        return datetime(ano, mes, dia).date()
            except:
                continue
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