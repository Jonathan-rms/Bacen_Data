import os
import requests
import zipfile
import io
import csv
import hashlib
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- CONFIGURAÇÕES DE FONTES ---
# Definimos as fontes, URLs e o sufixo do nome do arquivo esperado para cada uma.
SOURCES = [
    {
        "folder": "Prudencial",
        "url": "https://www.bcb.gov.br/content/estabilidadefinanceira/cosif/Conglomerados-prudenciais",
        "suffix": "BLOPRUDENCIAL"  # Ex: 202312BLOPRUDENCIAL.csv.zip
    },
    {
        "folder": "Sociedades",
        "url": "https://www.bcb.gov.br/content/estabilidadefinanceira/cosif/Sociedades",
        "suffix": "ESTBAN"         # Ex: 202312ESTBAN.csv.zip
    }
]

def gerar_anos_meses(inicio="202312"):
    """
    Gera lista de AnoMes (YYYYMM) de 'inicio' até o mês atual.
    """
    inicio_dt = datetime.strptime(inicio, "%Y%m")
    hoje = datetime.today()
    meses = []
    while inicio_dt <= hoje:
        meses.append(inicio_dt.strftime("%Y%m"))
        inicio_dt += relativedelta(months=1)
    return meses

def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def carregar_meta(caminho_meta: str) -> dict:
    if not os.path.exists(caminho_meta):
        return {}
    try:
        with open(caminho_meta, "r", encoding="utf-8") as f:
            lines = [l.strip().split(":", 1) for l in f if ":" in l]
            return {k.strip(): v.strip() for k, v in lines}
    except Exception:
        return {}

def salvar_meta(caminho_meta: str, headers: dict):
    try:
        with open(caminho_meta, "w", encoding="utf-8") as f:
            for k, v in headers.items():
                if v is not None:
                    f.write(f"{k}: {v}" + "\n")
    except Exception as e:
        print(f"⚠️ Erro ao salvar meta {caminho_meta}: {e}")

def baixar_e_descompactar(ano_mes: str, source_config: dict, force=False):
    """
    Baixa o arquivo ZIP do Bacen baseado na configuração da fonte.
    """
    ano = ano_mes[:4]
    base_url = source_config['url']
    suffix = source_config['suffix']
    folder_name = source_config['folder']

    # Organiza em subpastas: Balancetes/Prudencial/2024 ou Balancetes/Sociedades/2024
    pasta = f"Balancetes/{folder_name}/{ano}"
    os.makedirs(pasta, exist_ok=True)

    arquivo_zip = f"{ano_mes}{suffix}.csv.zip"
    url = f"{base_url}/{arquivo_zip}"
    caminho_csv = os.path.join(pasta, f"{ano_mes}{suffix}.csv")
    caminho_meta = caminho_csv + ".meta"

    print(f"➡️ [{folder_name}] Processando {url} ...")

    # Se não existe local, simplesmente baixa
    if not os.path.exists(caminho_csv) or force:
        _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, folder_name)
        return

    # Se local existe, tenta HEAD para comparar headers
    try:
        head = requests.head(url, timeout=30, allow_redirects=True)
    except Exception as e:
        print(f"⚠️ [{folder_name}/{ano_mes}] HEAD falhou: {e} — farei comparação via download.")
        head = None

    if head is not None and head.status_code == 200:
        headers = head.headers
        relevant = {
            "ETag": headers.get("ETag"),
            "Last-Modified": headers.get("Last-Modified"),
            "Content-Length": headers.get("Content-Length")
        }
        meta = carregar_meta(caminho_meta)

        if meta and all((meta.get(k) == v for k, v in relevant.items())):
            print(f"✔️ [{folder_name}/{ano_mes}] Sem mudanças (meta igual), pulando.")
            return
        else:
            print(f"🔁 [{folder_name}/{ano_mes}] Mudança detectada. Baixando...")
            _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, folder_name, headers=relevant)
            return
    else:
        print(f"ℹ️ [{folder_name}/{ano_mes}] HEAD indisponível (HTTP {head.status_code if head else 'N/A'}). Baixando para hash.")
        _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, folder_name, compare_hash=True)
        return

def _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, folder_name, headers=None, compare_hash=False):
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"❌ [{folder_name}/{ano_mes}] Não encontrado (HTTP {r.status_code}) - URL: {url}")
            return

        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nomes = z.namelist()
            # print(f"📦 Arquivos no zip: {nomes}")
            
            nome_csv = None
            for nome in nomes:
                if nome.lower().endswith(".csv"):
                    nome_csv = nome
                    break
            if not nome_csv:
                print(f"⚠️ [{folder_name}/{ano_mes}] ZIP sem CSV conhecido.")
                return

            with z.open(nome_csv) as f_in:
                csv_bytes = f_in.read()

            # Funções auxiliares para salvar meta
            def save_current_meta():
                meta_to_save = headers or {
                    "ETag": r.headers.get("ETag"),
                    "Last-Modified": r.headers.get("Last-Modified"),
                    "Content-Length": r.headers.get("Content-Length")
                }
                salvar_meta(caminho_meta, meta_to_save)

            if not os.path.exists(caminho_csv):
                with open(caminho_csv, "wb") as f_out:
                    f_out.write(csv_bytes)
                save_current_meta()
                print(f"✅ [{folder_name}/{ano_mes}] CSV salvo.")
                return

            if compare_hash:
                local_hash = sha256_file(caminho_csv)
                remote_hash = sha256_bytes(csv_bytes)
                if local_hash == remote_hash:
                    print(f"✔️ [{folder_name}/{ano_mes}] Hash idêntico.")
                    save_current_meta()
                    return
                else:
                    with open(caminho_csv, "wb") as f_out:
                        f_out.write(csv_bytes)
                    save_current_meta()
                    print(f"🔄 [{folder_name}/{ano_mes}] Hash diferente -> Atualizado.")
                    return

            # Se headers forçaram atualização ou fallback
            with open(caminho_csv, "wb") as f_out:
                f_out.write(csv_bytes)
            save_current_meta()
            print(f"✅ [{folder_name}/{ano_mes}] Atualizado.")

    except zipfile.BadZipFile:
        print(f"⚠️ [{folder_name}/{ano_mes}] Arquivo não é ZIP válido.")
    except Exception as e:
        print(f"⚠️ [{folder_name}/{ano_mes}] Erro: {e}")

def atualizar_balancetes(force=False):
    """
    Atualiza incrementalmente os balancetes para todas as fontes configuradas.
    """
    meses = gerar_anos_meses(inicio="202312")
    
    for source in SOURCES:
        print(f"\n--- Iniciando atualização: {source['folder']} ---")
        for mes in meses:
            baixar_e_descompactar(mes, source, force=force)

def gerar_index():
    """
    Gera um index_balancetes.csv mapeando TODAS as pastas (Prudencial e Sociedades).
    """
    root_dir = "Balancetes"
    if not os.path.exists(root_dir):
        print("Pasta Balancetes não existe. Nada a indexar.")
        return

    linhas = []
    base_raw = "https://raw.githubusercontent.com/Jonathan-rms/Bacen_Data/main"

    for dirpath, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".csv") and "index_balancetes" not in file.lower():
                # Força extensão maiúscula para consistência se necessário
                # file_upper = file[:-4] + ".CSV" 
                # (Se quiser manter o nome original do arquivo, use 'file')
                file_final = file 
                
                caminho_rel = os.path.join(dirpath, file_final).replace("\\", "/")
                url = f"{base_raw}/{caminho_rel}"
                
                # Tenta extrair AnoMes do início do arquivo (ex: 202312BLOPRUDENCIAL -> 202312)
                ano_mes = file[:6]
                
                # Identifica tipo baseado na pasta ou nome
                tipo = "Indefinido"
                if "Prudencial" in dirpath:
                    tipo = "Prudencial"
                elif "Sociedades" in dirpath:
                    tipo = "Sociedades"

                linhas.append([ano_mes, tipo, url])

    index_path = os.path.join(root_dir, "index_balancetes.csv")
    with open(index_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ano_mes", "tipo", "link"])
        # Ordena por ano_mes e depois por tipo
        for linha in sorted(linhas, key=lambda x: (x[0], x[1])):
            writer.writerow(linha)

    print(f"✅ {index_path} gerado com {len(linhas)} entradas.")

if __name__ == "__main__":
    import sys
    force_flag = "--force" in sys.argv
    atualizar_balancetes(force=force_flag)
    gerar_index()
