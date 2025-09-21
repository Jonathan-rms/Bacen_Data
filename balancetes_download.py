import os
import requests
import zipfile
import io
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
                # Salva cada arquivo contido no ZIP (geralmente apenas 1 CSV)
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
    # Ajuste aqui o ponto de início -> Dezembro/2023 (202312) funciona bem
    meses = gerar_anos_meses(inicio="202312")

    for mes in meses:
        baixar_e_descompactar(mes)

if __name__ == "__main__":
    atualizar_balancetes()
