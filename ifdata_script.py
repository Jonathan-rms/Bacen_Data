import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging
import os

# ===== LOGGING =====
logging.basicConfig(
    filename="IFDATA_LOG.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def gerar_anos_meses(inicio="202412"):
    """Gera lista de AnoMes até o mês atual"""
    inicio_dt = datetime.strptime(inicio, "%Y%m")
    hoje = datetime.today()
    meses = []
    while inicio_dt <= hoje:
        meses.append(inicio_dt.strftime("%Y%m"))
        inicio_dt += relativedelta(months=1)
    return meses

def fetch_mes(ano_mes):
    """Puxa dados de 1 mês"""
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
        f"IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
        f"?@AnoMes={ano_mes}&@TipoInstituicao=1&@Relatorio='1'&$format=json"
    )
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        dados = response.json().get("value", [])
        if dados:
            return pd.DataFrame(dados)
    except Exception as e:
        logging.error(f"Erro ao ler {ano_mes}: {e}")
    return None

def atualizar_ifdata():
    logging.info("Iniciando execução incremental...")
    df_final = pd.DataFrame()

    # Se já existe histórico, carregamos
    if os.path.exists("IFDATA_Historico.csv"):
        df_final = pd.read_csv("IFDATA_Historico.csv", encoding="utf-8-sig")
        # Identifica último mês carregado
        if "AnoMes" in df_final.columns:
            ultimo_mes = str(df_final["AnoMes"].max())
        else:
            ultimo_mes = "202412"
    else:
        ultimo_mes = "202412"

    logging.info(f"Último mês registrado: {ultimo_mes}")

    # Próximos meses até hoje
    inicio_proximo = datetime.strptime(ultimo_mes, "%Y%m") + relativedelta(months=1)
    lista = gerar_anos_meses(inicio=inicio_proximo.strftime("%Y%m"))

    if not lista:
        logging.info("Nenhum mês novo disponível. Nada para atualizar.")
        return

    logging.info(f"Buscando novos meses: {lista}")

    dfs_novos = []
    for mes in lista:
        df_mes = fetch_mes(mes)
        if df_mes is not None:
            dfs_novos.append(df_mes)

    if dfs_novos:
        df_novo = pd.concat(dfs_novos, ignore_index=True)
        df_final = pd.concat([df_final, df_novo], ignore_index=True)
        df_final.to_csv("IFDATA_Historico.csv", index=False, encoding="utf-8-sig")
        logging.info(f"Atualização concluída. Meses adicionados: {lista}")
    else:
        logging.info("Nenhum dado novo capturado.")

if __name__ == "__main__":
    atualizar_ifdata()
