from flask import Flask, request, jsonify
from datetime import datetime
import re
import tempfile
import os

app = Flask(__name__)

def extrair_texto_pdf(file_path):
    """Extrai texto de PDF"""
    try:
        import PyPDF2
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            texto = ""
            for pagina in reader.pages:
                texto += pagina.extract_text()
            return texto.lower()
    except:
        return ""

def encontrar_valor(texto):
    """Encontra valor no texto"""
    padroes = [
        r'r\$\s*(\d+[.,]\d{2})',
        r'valor\s*[:\s]*r\$\s*(\d+[.,]\d{2})',
        r'(\d+[.,]\d{2})\s*reais',
    ]
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto)
        for valor in encontrados:
            try:
                if isinstance(valor, tuple):
                    valor_str = valor[-1]
                else:
                    valor_str = valor
                
                valor_str = valor_str.replace(',', '.')
                return float(valor_str)
            except:
                continue
    return None

def encontrar_data(texto):
    """Encontra data no texto"""
    meses = {
        'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
    }
    
    padroes = [
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'(\d{1,2})\s*(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s*(\d{4})',
    ]
    
    for padrao in padroes:
        encontrados = re.findall(padrao, texto)
        for data in encontrados:
            if len(data) == 3:
                try:
                    dia = int(data[0])
                    mes_abrev = data[1].lower()
                    ano = int(data[2])
                    
                    if mes_abrev in meses:
                        mes = meses[mes_abrev]
                        return datetime(ano, mes, dia).date()
                except:
                    continue
            else:
                data_str = data[0] if isinstance(data, tuple) else data
                for formato in ['%d/%m/%Y', '%d-%m-%Y']:
                    try:
                        return datetime.strptime(data_str, formato).date()
                    except:
                        continue
    return None

@app.route('/validar', methods=['POST'])
def validar_comprovante():
    try:
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({
                'valido': False,
                'erro': 'Nenhum arquivo enviado'
            }), 400
        
        arquivo = request.files['file']
        valor_esperado = request.form.get('valor_esperado')
        
        if not valor_esperado:
            return jsonify({
                'valido': False,
                'erro': 'Valor esperado não informado'
            }), 400
        
        # Converter valor para float
        try:
            valor_esperado = float(valor_esperado)
        except:
            return jsonify({
                'valido': False,
                'erro': 'Valor esperado deve ser um número'
            }), 400
        
        if arquivo.filename == '':
            return jsonify({
                'valido': False,
                'erro': 'Nenhum arquivo selecionado'
            }), 400
        
        if not arquivo.filename.lower().endswith('.pdf'):
            return jsonify({
                'valido': False,
                'erro': 'Apenas arquivos PDF são aceitos'
            }), 400
        
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
        
        # VALIDAÇÕES
        if valor_encontrado is None:
            return jsonify({
                'valido': False,
                'erro': 'Não foi possível encontrar o valor no comprovante'
            }), 200
        
        if data_encontrada is None:
            return jsonify({
                'valido': False,
                'erro': 'Não foi possível encontrar a data no comprovante'
            }), 200
        
        # Verificar valor
        if valor_encontrado != valor_esperado:
            return jsonify({
                'valido': False,
                'erro': 'Valor incorreto'
            }), 200
        
        # Verificar data
        if data_encontrada != data_hoje:
            return jsonify({
                'valido': False,
                'erro': 'Data incorreta'
            }), 200
        
        # Tudo certo
        return jsonify({
            'valido': True
        }), 200
        
    except Exception as e:
        return jsonify({
            'valido': False,
            'erro': 'Erro ao processar comprovante'
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API funcionando'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"✅ API rodando na porta {port}")
    app.run(host='0.0.0.0', port=port, debug=False)