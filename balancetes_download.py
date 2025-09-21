import os
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
import zipfile
import io

BASE_URL = "https://www.bcb.gov.br/content/estabilidadefinanceira/cosif/Sociedades"

def gerar_anos_meses(inicio="202412"):
    inicio_dt = datetime.strptime(inicio, "%Y%m")
    hoje = datetime.today()
    meses = []
    while inicio_dt <= hoje:
        meses.append(inicio_dt.strftime("%Y%m"))
        inicio_dt += relativedelta(months=1)
    return meses

def baixar_e_descompactar(ano_mes):
    ano = ano_mes[:4]
    arquivo_zip = f"{ano_mes}SOCIEDADES.csv.zip"
    url = f"{BASE_URL}/{arquivo_zip}"
    pasta = f"Balancetes/{ano}"
    os.makedirs(pasta, exist_ok=True)

    # Nome final do CSV
    caminho_csv = os.path.join(pasta, f"{ano_mes}SOCIEDADES.csv")
    if os.path.exists(caminho_csv):
        print(f"[{ano_mes}] já existe CSV, pulando...")
        return

    try:
        print(f"[{ano_mes}] Baixando {url} ...")
        r = requests.get(url, timeout=60)
        if r.status_code == 200:
            # Lê o zip em memória
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                for nome in z.namelist():
                    if nome.endswith(".csv"):
                        with z.open(nome) as f_in, open(caminho_csv, "wb") as f_out:
                            f_out.write(f_in.read())
                        print(f"[{ano_mes}] CSV salvo em {caminho_csv}")
        else:
            print(f"[{ano_mes}] Não encontrado (HTTP {r.status_code})")
    except Exception as e:
        print(f"[{ano_mes}] Erro: {e}")

def atualizar_balancetes():
    meses = gerar_anos_meses(inicio="202412")
    for mes in meses:
        baixar_e_descompactar(mes)

if __name__ == "__main__":
    atualizar_balancetes()
