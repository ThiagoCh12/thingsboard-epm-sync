from dotenv import load_dotenv
import os

load_dotenv()

#THINGSBOARDS
TB_URL = os.getenv("TB_URL")
TB_USER = os.getenv("TB_USER")
TB_PASSWORD = os.getenv("TB_PASSWORD")
ASSET_ID = "6ab04290-4af3-11f0-a50c-0128cde99c08"
telemetry_key = "Nível em Cota"

#EPM
EPM_API = os.getenv("EPM_API")
EPM_AUTH = os.getenv("EPM_AUTH")
EPM_USER = os.getenv("EPM_USER")
EPM_PASSWORD = os.getenv("EPM_PASSWORD")

#GERAIS
polling_interval = 1800
token_validade = 3600
max_erros_consecutivos =  10
heartbeat_interval = 300
recarregar_variaveis_a_cada = 4

def validar_config():
    """Valida se todas as variáveis obrigatórias estão configuradas"""
    obrigatorias = {
        "TB_URL": TB_URL,
        "TB_USER": TB_USER,
        "TB_PASSWORD": TB_PASSWORD,
        "EPM_API": EPM_API,
        "EPM_AUTH": EPM_AUTH,
        "EPM_USER": EPM_USER,
        "EPM_PASSWORD": EPM_PASSWORD,
    }
    
    faltando = [nome for nome, valor in obrigatorias.items() if not valor]
    
    if faltando:
        raise ValueError(f"❌ Variáveis obrigatórias não configuradas: {', '.join(faltando)}")

validar_config()