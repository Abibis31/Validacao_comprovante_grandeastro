from flask import Flask, request, jsonify
from datetime import datetime
import re
import tempfile
import os

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online", 
        "message": "API de validacao de comprovantes para Manny Chat",
        "uso": "Envie um PDF com comprovante via POST /validar"
    })

def detectar_tipo_arquivo(arquivo):
    """
    Detecta se o arquivo é PDF, imagem ou texto
    """
    try:
        filename = arquivo.filename.lower()
        
        # Verificar extensões de imagem
        extensoes_imagem = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.heic', '.tiff']
        if any(filename.endswith(ext) for ext in extensoes_imagem):
            return "imagem"
        
        # Verificar se é PDF
        if filename.endswith('.pdf'):
            return "pdf"
            
        # Verificação por conteúdo
        arquivo.seek(0)
        primeiros_bytes = arquivo.read(1024)
        arquivo.seek(0)
        
        if primeiros_bytes.startswith(b'%PDF'):
            return "pdf"
        elif primeiros_bytes.startswith((b'\xFF\xD8\xFF', b'\x89PNG', b'GIF', b'BM')):
            return "imagem"
        else:
            return "outro"
                
    except Exception:
        return "desconhecido"

def extrair_texto_pdf(file_path):
    """Extrai texto de PDF usando pdfplumber (mais eficiente)"""
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
        # Fallback para PyPDF2
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                texto = ""
                for pagina in reader.pages:
                    texto += pagina.extract_text() or ""
            return texto.lower()
        except:
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
                
                # Converter para float e depois para inteiro (remove centavos)
                valor_str = valor_str.replace(',', '.')
                valor_float = float(valor_str)
                return int(valor_float)  # Retorna apenas a parte inteira
            except:
                continue
    return None

def encontrar_data(texto):
    """Encontra data no texto - versão melhorada"""
    # Padrões de data mais flexíveis
    padroes = [
        # DD/MM/AAAA
        r'(\d{1,2})/(\d{1,2})/(\d{4})',
        # DD-MM-AAAA
        r'(\d{1,2})-(\d{1,2})-(\d{4})',
        # DD.MM.AAAA
        r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
        # AAAA-MM-DD
        r'(\d{4})-(\d{1,2})-(\d{1,2})',
        # DD/MM/AA (ano com 2 dígitos)
        r'(\d{1,2})/(\d{1,2})/(\d{2})',
    ]
    
    datas_encontradas = []
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto)
        for match in encontrados:
            try:
                if len(match) == 3:
                    if len(match[2]) == 2:  # Ano com 2 dígitos
                        ano = int("20" + match[2])  # Assume século 21
                    else:
                        ano = int(match[2])
                    
                    # Verificar formato da data
                    if '/' in texto or '-' in texto or '.' in texto:
                        # Formato DD/MM/AAAA ou DD-MM-AAAA
                        dia = int(match[0])
                        mes = int(match[1])
                    else:
                        # Formato AAAA-MM-DD
                        dia = int(match[2])
                        mes = int(match[1])
                        ano = int(match[0])
                    
                    # Validar se é uma data real
                    if 1 <= dia <= 31 and 1 <= mes <= 12 and 2020 <= ano <= 2030:
                        data_obj = datetime(ano, mes, dia).date()
                        datas_encontradas.append(data_obj)
                        
            except:
                continue
    
    # Retornar a data mais recente encontrada
    if datas_encontradas:
        return max(datas_encontradas)
    
    return None

@app.route('/validar', methods=['POST'])
def validar_comprovante():
    try:
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Nenhum arquivo enviado'
            }), 400
        
        arquivo = request.files['file']
        
        if arquivo.filename == '':
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Nenhum arquivo selecionado'
            }), 400
        
        # DETECTAR TIPO DE ARQUIVO
        tipo_arquivo = detectar_tipo_arquivo(arquivo)
        
        # Se for imagem, retorna falso imediatamente
        if tipo_arquivo == "imagem":
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Arquivo de imagem não é aceito'
            }), 200
        
        # Se não for PDF, retorna falso
        if tipo_arquivo != "pdf":
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Apenas arquivos PDF são aceitos'
            }), 200
        
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
        
        # DEBUG: Mostrar o que foi encontrado
        print(f"Texto extraído: {texto[:500]}...")
        print(f"Valor encontrado: {valor_encontrado}")
        print(f"Data encontrada: {data_encontrada}")
        print(f"Data hoje: {data_hoje}")
        
        # VALIDAÇÕES SIMPLIFICADAS
        if valor_encontrado is None:
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Não foi possível encontrar o valor no comprovante'
            }), 200
        
        if data_encontrada is None:
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': 'Não foi possível encontrar a data no comprovante'
            }), 200
        
        # Verificar data - deve ser de hoje
        if data_encontrada != data_hoje:
            return jsonify({
                'sucesso': False,
                'valor': None,
                'mensagem': f'Comprovante não é de hoje (data: {data_encontrada})'
            }), 200
        
        # Tudo certo - retorna o valor inteiro
        return jsonify({
            'sucesso': True,
            'valor': valor_encontrado,
            'mensagem': f'Comprovante válido no valor de R$ {valor_encontrado},00'
        }), 200
        
    except Exception as e:
        return jsonify({
            'sucesso': False,
            'valor': None,
            'mensagem': f'Erro ao processar comprovante: {str(e)}'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API funcionando'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"API Manny Chat rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)