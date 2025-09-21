import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

# ===== LOGGING =====
logging.basicConfig(
    filename="IFDATA_LOG.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def gerar_anos_meses(inicio="202403"):
    """Gera lista de AnoMes até o mês atual"""
    inicio_dt = datetime.strptime(inicio, "%Y%m")
    hoje = datetime.today()
    meses = []
    while inicio_dt <= hoje:
        meses.append(inicio_dt.strftime("%Y%m"))
        inicio_dt += relativedelta(months=1)
    return meses


def atualizar_ifdata():
    """Função principal que coleta os dados e gera CSV"""
    logging.info("Iniciando execução do script...")
    try:
        anos_meses = gerar_anos_meses()
        df_final = pd.DataFrame()

        for ano_mes in anos_meses:
            logging.info(f"Lendo dados do mês {ano_mes}...")
            url = (
                "https://olinda.bcb.gov.br/olinda/servico/IFDATA/versao/v1/odata/"
                f"IfDataValores(AnoMes=@AnoMes,TipoInstituicao=@TipoInstituicao,Relatorio=@Relatorio)"
                f"?@AnoMes={ano_mes}&@TipoInstituicao=1&@Relatorio='1'&$format=json"
            )
            try:
                response = requests.get(url)
                response.raise_for_status()
                dados = response.json().get("value", [])
                if dados:
                    df = pd.DataFrame(dados)
                    df_final = pd.concat([df_final, df], ignore_index=True)
            except Exception as e:
                logging.error(f"Erro ao ler {ano_mes}: {e}")

        # Salva CSV
        df_final.to_csv("IFDATA_Historico.csv", index=False, encoding="utf-8-sig")
        logging.info("Arquivo CSV gerado com sucesso.")

    except Exception as e:
        logging.error(f"Erro geral na execução: {e}")


if __name__ == "__main__":
    atualizar_ifdata()
