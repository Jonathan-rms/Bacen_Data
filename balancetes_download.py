import os
import requests
import zipfile
import io
import csv
from datetime import datetime
from dateutil.relativedelta import relativedelta

# URL base do Bacen
BASE_URL = "https://www.bcb.gov.br/content/estabilidadefinanceira/cosif/Sociedades"

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

def baixar_e_descompactar(ano_mes: str):
    """
    Baixa o arquivo ZIP do Bacen para o mês informado e extrai o CSV.
    """
    ano = ano_mes[:4]
    pasta = f"Balancetes/{ano}"
    os.makedirs(pasta, exist_ok=True)

    arquivo_zip = f"{ano_mes}SOCIEDADES.csv.zip"
    url = f"{BASE_URL}/{arquivo_zip}"
    caminho_csv = os.path.join(pasta, f"{ano_mes}SOCIEDADES.csv")

    print(f"➡️ Tentando baixar {url} ...")

    # Se já existe o CSV, não baixa de novo
    if os.path.exists(caminho_csv):
        print(f"✔️ [{ano_mes}] já existe ({caminho_csv}), pulando.")
        return

    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            print(f"❌ [{ano_mes}] Não encontrado (HTTP {r.status_code})")
            return

        # Tenta abrir como arquivo zip
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            print(f"📦 Arquivos dentro do zip ({ano_mes}): {z.namelist()}")
            for nome in z.namelist():
                # Salva cada arquivo contido no ZIP
                caminho_final = os.path.join(pasta, nome)
                with z.open(nome) as f_in, open(caminho_final, "wb") as f_out:
                    f_out.write(f_in.read())
                print(f"✅ [{ano_mes}] CSV extraído para {caminho_final}")

    except zipfile.BadZipFile:
        print(f"⚠️ [{ano_mes}] O arquivo baixado não é um ZIP válido (talvez o Bacen ainda não publicou).")
    except Exception as e:
        print(f"⚠️ [{ano_mes}] Erro inesperado: {e}")

def atualizar_balancetes():
    """
    Atualiza incrementalmente os balancetes disponíveis.
    """
    meses = gerar_anos_meses(inicio="202312")
    for mes in meses:
        baixar_e_descompactar(mes)

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
    atualizar_balancetes()
    gerar_index()
