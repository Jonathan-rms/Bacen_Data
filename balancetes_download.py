import os
import requests
import zipfile
import io
import csv
import hashlib
from datetime import datetime
from dateutil.relativedelta import relativedelta

# URL base do Bacen
BASE_URL = "https://www.bcb.gov.br/content/estabilidadefinanceira/cosif/Conglomerados-prudenciais"

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

def baixar_e_descompactar(ano_mes: str, force=False):
    """
    Baixa o arquivo ZIP do Bacen para o mês informado e extrai o CSV.
    Se já existir o CSV, tenta checar se o remoto mudou (ETag/Last-Modified/Content-Length).
    Se o servidor não fornecer cabeçalhos confiáveis, baixa e compara hash do CSV.
    """
    ano = ano_mes[:4]
    pasta = f"Balancetes/{ano}"
    os.makedirs(pasta, exist_ok=True)

    arquivo_zip = f"{ano_mes}SOCIEDADES.csv.zip"
    url = f"{BASE_URL}/{arquivo_zip}"
    caminho_csv = os.path.join(pasta, f"{ano_mes}SOCIEDADES.csv")
    caminho_meta = caminho_csv + ".meta"

    print(f"➡️ Tentando processar {url} ...")

    # Se não existe local, simplesmente baixa
    if not os.path.exists(caminho_csv) or force:
        _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes)
        return

    # Se local existe, tenta HEAD para comparar headers
    try:
        head = requests.head(url, timeout=30, allow_redirects=True)
    except Exception as e:
        print(f"⚠️ [{ano_mes}] HEAD falhou: {e} — farei comparação via download se necessário.")
        head = None

    if head is not None and head.status_code == 200:
        headers = head.headers
        relevant = {
            "ETag": headers.get("ETag"),
            "Last-Modified": headers.get("Last-Modified"),
            "Content-Length": headers.get("Content-Length")
        }
        meta = carregar_meta(caminho_meta)

        # Se meta existe e igual, pulamos
        if meta and all((meta.get(k) == v for k, v in relevant.items())):
            print(f"✔️ [{ano_mes}] sem mudanças detectadas via HEAD (meta igual), pulando.")
            return
        else:
            print(f"🔁 [{ano_mes}] mudança detectada via HEAD ou meta ausente/diferente. Baixando para comparar/atualizar...")
            _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, headers=relevant)
            return
    else:
        # HEAD não disponível / 404 etc -> fallback: baixar e comparar hashes (pode baixar mesmo se sem mudança)
        print(f"ℹ️ [{ano_mes}] HEAD indisponível ou não retornou 200 (status {head.status_code if head else 'N/A'}). Fazendo download e comparando hash do CSV.")
        _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, compare_hash=True)
        return

def _baixar_e_salvar(url, caminho_csv, caminho_meta, ano_mes, headers=None, compare_hash=False):
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"❌ [{ano_mes}] Não encontrado (HTTP {r.status_code})")
            return

        # Tenta abrir como arquivo zip
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            nomes = z.namelist()
            print(f"📦 Arquivos dentro do zip ({ano_mes}): {nomes}")
            # Escolhe o primeiro CSV encontrado (case-insensitive)
            nome_csv = None
            for nome in nomes:
                if nome.lower().endswith(".csv"):
                    nome_csv = nome
                    break
            if not nome_csv:
                print(f"⚠️ [{ano_mes}] ZIP não contém CSV conhecido.")
                return

            with z.open(nome_csv) as f_in:
                csv_bytes = f_in.read()

            # Se o CSV não existe local, salvar
            if not os.path.exists(caminho_csv):
                with open(caminho_csv, "wb") as f_out:
                    f_out.write(csv_bytes)
                # salvar meta se headers foram informados
                meta_to_save = headers or {
                    "ETag": r.headers.get("ETag"),
                    "Last-Modified": r.headers.get("Last-Modified"),
                    "Content-Length": r.headers.get("Content-Length")
                }
                salvar_meta(caminho_meta, meta_to_save)
                print(f"✅ [{ano_mes}] CSV salvo em {caminho_csv}")
                return

            # Se existe e queremos comparar por hash
            if compare_hash:
                local_hash = sha256_file(caminho_csv)
                remote_hash = sha256_bytes(csv_bytes)
                if local_hash == remote_hash:
                    print(f"✔️ [{ano_mes}] CSV local igual ao remoto (hash), sem alteração.")
                    # ainda atualiza meta básica se disponível
                    meta_to_save = {
                        "ETag": r.headers.get("ETag"),
                        "Last-Modified": r.headers.get("Last-Modified"),
                        "Content-Length": r.headers.get("Content-Length")
                    }
                    salvar_meta(caminho_meta, meta_to_save)
                    return
                else:
                    with open(caminho_csv, "wb") as f_out:
                        f_out.write(csv_bytes)
                    meta_to_save = {
                        "ETag": r.headers.get("ETag"),
                        "Last-Modified": r.headers.get("Last-Modified"),
                        "Content-Length": r.headers.get("Content-Length")
                    }
                    salvar_meta(caminho_meta, meta_to_save)
                    print(f"🔄 [{ano_mes}] CSV local atualizado por diferença de conteúdo (hash).")
                    return

            # Se headers foram passados (do HEAD) e detectamos diferença, substituímos e atualizamos meta
            if headers is not None:
                # Substitui diretamente
                with open(caminho_csv, "wb") as f_out:
                    f_out.write(csv_bytes)
                salvar_meta(caminho_meta, headers)
                print(f"🔄 [{ano_mes}] CSV atualizado com base em HEAD/headers.")
                return

            # Caso não tenha entrado em nenhuma condição, por segurança sobrescrever
            with open(caminho_csv, "wb") as f_out:
                f_out.write(csv_bytes)
            meta_to_save = {
                "ETag": r.headers.get("ETag"),
                "Last-Modified": r.headers.get("Last-Modified"),
                "Content-Length": r.headers.get("Content-Length")
            }
            salvar_meta(caminho_meta, meta_to_save)
            print(f"✅ [{ano_mes}] CSV salvo/atualizado em {caminho_csv}")

    except zipfile.BadZipFile:
        print(f"⚠️ [{ano_mes}] O arquivo baixado não é um ZIP válido (talvez o Bacen ainda não publicou).")
    except Exception as e:
        print(f"⚠️ [{ano_mes}] Erro inesperado: {e}")

def atualizar_balancetes(force=False):
    """
    Atualiza incrementalmente os balancetes disponíveis.
    """
    meses = gerar_anos_meses(inicio="202312")
    for mes in meses:
        baixar_e_descompactar(mes, force=force)

def gerar_index():
    """
    Gera um arquivo Balancetes/index_balancetes.csv com todos os links RAW dos CSVs
    """
    root_dir = "Balancetes"
    linhas = []

    # URL base correta para RAW
    base_raw = "https://raw.githubusercontent.com/Jonathan-rms/Bacen_Data/main"

    for dirpath, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(".csv") and "index_balancetes" not in file.lower():
                # Força extensão maiúscula
                file_upper = file[:-4] + ".CSV"

                # Caminho relativo, garantindo separadores "/"
                caminho_rel = os.path.join(dirpath, file_upper).replace("\\", "/")

                url = f"{base_raw}/{caminho_rel}"
                ano_mes = file.split("SOCIEDADES")[0]
                linhas.append([ano_mes, url])

    # Salvar o index dentro de Balancetes/
    index_path = os.path.join(root_dir, "index_balancetes.csv")

    with open(index_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ano_mes", "link"])
        for linha in sorted(linhas, key=lambda x: x[0]):
            writer.writerow(linha)

    print(f"✅ {index_path} gerado com {len(linhas)} entradas.")

if __name__ == "__main__":
    # Para forçar re-download de todos, rode python balancetes_download.py --force
    import sys
    force_flag = "--force" in sys.argv
    atualizar_balancetes(force=force_flag)
    gerar_index()
