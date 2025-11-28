import epmwebapi as epm
import requests
import json
import config
import datetime
import time
import logging
from logging.handlers import RotatingFileHandler
import urllib3
from functools import wraps

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===============================================================
# 🔧 CONFIGURAÇÃO DE LOGS COM ROTAÇÃO
# ===============================================================
handler = RotatingFileHandler(
    'sync.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
handler.setLevel(logging.DEBUG)

console = logging.StreamHandler()
console.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
console.setFormatter(formatter)

logging.basicConfig(
    level=logging.DEBUG,
    handlers=[handler, console]
)

# ===============================================================
# CARREGAR CONFIGURAÇÕES
# ===============================================================

with open("mapping.json", "r", encoding="utf-8") as f:
    mapping = json.load(f)

TB_URL = config.TB_URL
TB_USER = config.TB_USER
TB_PASSWORD = config.TB_PASSWORD

EPM_API = config.EPM_API
EPM_AUTH = config.EPM_AUTH
EPM_USER = config.EPM_USER
EPM_PASSWORD = config.EPM_PASSWORD

polling = config.polling_interval
chave_telemetria = config.telemetry_key
asset_id = config.ASSET_ID

# Configurações adicionais
TOKEN_VALIDADE = config.token_validade
MAX_ERROS_CONSECUTIVOS = config.max_erros_consecutivos
HEARTBEAT_INTERVAL = config.heartbeat_interval

# ===============================================================
# 🔄 FUNÇÃO PARA RENOVAR TOKEN AUTOMATICAMENTE
# ===============================================================
def obter_token_thingsboard():
    """Obtém novo token do ThingsBoard"""
    try:
        resp = requests.post(
            f"{TB_URL}/api/auth/login",
            json={"username": TB_USER, "password": TB_PASSWORD},
            verify=False,
            timeout=10
        )
        resp.raise_for_status()
        token = resp.json()["token"]
        logging.info("✅ Token ThingsBoard renovado")
        return token, time.time()
    except Exception as e:
        logging.error(f"❌ Erro ao obter token: {e}")
        return None, None

# ===============================================================
# 🔄 RECONEXÃO AUTOMÁTICA COM EPM
# ===============================================================
def conectar_epm(max_tentativas=3):
    """Conecta ao EPM com retry"""
    for tentativa in range(1, max_tentativas + 1):
        try:
            logging.info(f"🔗 Tentativa {tentativa}/{max_tentativas} - Conectando ao EPM...")
            connection = epm.EpmConnection(
                EPM_API,
                EPM_AUTH,
                EPM_USER,
                EPM_PASSWORD
            )
            logging.info("✅ Conectado ao EPM Server")
            return connection
        except Exception as e:
            logging.error(f"❌ Falha na tentativa {tentativa}: {e}")
            if tentativa < max_tentativas:
                time.sleep(5 * tentativa)  # Backoff exponencial
    return None

# ===============================================================
# 🔄 GERENCIAMENTO DE TOKEN
# ===============================================================
token = None
token_timestamp = 0

def obter_headers():
    """Retorna headers com token válido"""
    global token, token_timestamp
    
    # Renovar token se expirado ou próximo de expirar (5 min de margem)
    if token is None or (time.time() - token_timestamp) > (TOKEN_VALIDADE - 300):
        token, token_timestamp = obter_token_thingsboard()
        if token is None:
            raise Exception("Não foi possível obter token do ThingsBoard")
    
    return {"X-Authorization": f"Bearer {token}"}

# ===============================================================
# CONECTAR AO EPM SERVER
# ===============================================================
connection = conectar_epm()
if connection is None:
    logging.error("❌ Não foi possível conectar ao EPM após várias tentativas")
    exit(1)

# ===============================================================
# AUTENTICAR NO THINGSBOARD
# ===============================================================
token, token_timestamp = obter_token_thingsboard()
if token is None:
    logging.error("❌ Não foi possível autenticar no ThingsBoard")
    connection.close()
    exit(1)

headers = obter_headers()

# ===============================================================
# BUSCAR DEVICES DO ASSET ESPECÍFICO
# ===============================================================
if asset_id:
    logging.info(f"🎯 Filtrando devices do Asset: {asset_id}")
    
    # Buscar informações do Asset
    asset_url = f"{TB_URL}/api/asset/{asset_id}"
    resp = requests.get(asset_url, headers=headers, verify=False, timeout=10)

    if resp.status_code == 200:
        asset_info = resp.json()
        asset_name = asset_info.get('name','N/A')
        logging.info(f"   Asset: {asset_name}")
    else:
        logging.error(f"❌ Asset não encontrado: {asset_id}")
        connection.close()
        exit(1)
    
    # Buscar devices relacionados ao Asset
    relations_url = f"{TB_URL}/api/relations/info"
    params = {
        "fromId": asset_id,
        "fromType": "ASSET"
    }
    
    resp = requests.get(relations_url, headers=headers, params=params, verify=False, timeout=10)
    relations = resp.json()
    
    # Filtrar apenas devices
    device_ids = []
    for relation in relations:
        if relation.get("to", {}).get("entityType") == "DEVICE":
            device_ids.append(relation["to"]["id"])
    
    logging.info(f"   Encontrados {len(device_ids)} device(s) relacionado(s)")
    
    # Buscar detalhes de cada device
    devices = []
    for dev_id in device_ids:
        device_url = f"{TB_URL}/api/device/{dev_id}"
        resp = requests.get(device_url, headers=headers, verify=False, timeout=10)
        if resp.status_code == 200:
            devices.append(resp.json())
    
else:
    logging.info(f"❌ Não foi possível encontrar os Dispositivos relacionados ao Asset: {asset_id}")
    
logging.info(f"📋 Total de devices encontrados: {len(devices)}")

# ===============================================================
# MAPEAR DEVICES PARA VARIÁVEIS EXISTENTES
# ===============================================================
logging.info("🔗 Mapeando devices para variáveis do EPM...")

device_map = {}
devices_nao_mapeados = []

for device in devices:
    device_name = device["name"]
    device_id = device["id"]["id"]
    
    # Buscar no mapeamento
    if device_name in mapping:
        var_path = mapping[device_name]
        device_map[device_id] = {
            "name": device_name,
            "var_path": var_path,
            "obj": None
        }
        logging.info(f"  ✅ {device_name} → {var_path}")
    else:
        devices_nao_mapeados.append(device_name)
        logging.warning(f"  ⚠️  {device_name} não está no mapping.json")

if devices_nao_mapeados:
    logging.warning(f"\n⚠️  {len(devices_nao_mapeados)} device(s) sem mapeamento:")
    for name in devices_nao_mapeados:
        logging.warning(f"     - {name}")
    logging.warning("   Adicione-os ao mapping.json para sincronizá-los\n")

if not device_map:
    logging.error("❌ NENHUM device foi mapeado!")
    connection.close()
    exit(1)

logging.info(f"✅ {len(device_map)} devices mapeados")

# ===============================================================
# CARREGAR OBJETOS DAS VARIÁVEIS 
# ===============================================================
logging.info("🔍 Carregando variáveis do EPM...")

variaveis_ok = 0
variaveis_nao_encontradas = []

for device_id, info in device_map.items():
    try:
        var_path = info["var_path"]
        
        # Carregar variável com caminho hierárquico
        bv_object = connection.getDataObjects(var_path)
        
        # Validação rigorosa
        if bv_object and isinstance(bv_object, dict) and var_path in bv_object and bv_object[var_path] is not None:
            info["obj"] = bv_object[var_path]
            variaveis_ok += 1
            logging.info(f"  ✅ {var_path}")
        else:
            info["obj"] = None
            variaveis_nao_encontradas.append(var_path)
            logging.warning(f"  ❌ Variável não encontrada: {var_path}")
            
    except Exception as e:
        info["obj"] = None
        variaveis_nao_encontradas.append(info["var_path"])
        logging.error(f"  ❌ Erro ao carregar {info['var_path']}: {e}")

logging.info(f"📊 {variaveis_ok}/{len(device_map)} variáveis carregadas com sucesso")

# Alertar sobre variáveis que precisam ser criadas
if variaveis_nao_encontradas:
    logging.warning("")
    logging.warning("=" * 70)
    logging.warning("⚠️  VARIÁVEIS QUE PRECISAM SER CRIADAS NO EPM STUDIO:")
    logging.warning("=" * 70)
    for var_path in variaveis_nao_encontradas:
        logging.warning(f"   - {var_path}")
    logging.warning("=" * 70)
    logging.warning("")

if variaveis_ok == 0:
    logging.error("❌ NENHUMA variável foi encontrada!")
    logging.error("   Crie as variáveis acima no EPM Studio antes de continuar.")
    connection.close()
    exit(1)

logging.info(f"ℹ️  Sincronização continuará apenas para as {variaveis_ok} variável(is) existente(s)")
logging.info("")

# ===============================================================
# VERIFICAR CHAVES DE TELEMETRIA DISPONÍVEIS
# ===============================================================
logging.info("🔍 Verificando chaves de telemetria disponíveis...")

# Pegar o primeiro device para testar
test_device_id = list(device_map.keys())[0]
test_device_name = device_map[test_device_id]["name"]

test_url = f"{TB_URL}/api/plugins/telemetry/DEVICE/{test_device_id}/keys/timeseries"
resp = requests.get(test_url, headers=headers, verify=False, timeout=10)
available_keys = resp.json()

logging.info(f"   Device de teste: {test_device_name}")
logging.info(f"   Chaves disponíveis: {available_keys}")
logging.info(f"   Chave configurada: '{chave_telemetria}'")

if chave_telemetria not in available_keys:
    logging.error(f"❌ A chave '{chave_telemetria}' NÃO existe!")
    logging.error(f"   Chaves válidas: {', '.join(available_keys)}")
    logging.error(f"   Atualize o 'telemetry_key' no config.json")
    connection.close()
    exit(1)
else:
    logging.info(f"   ✅ Chave '{chave_telemetria}' encontrada!")

logging.info("")

# ===============================================================
# 📊 HEARTBEAT
# ===============================================================
ultimo_heartbeat = time.time()

def log_heartbeat():
    global ultimo_heartbeat
    if time.time() - ultimo_heartbeat > HEARTBEAT_INTERVAL:
        logging.info(f"💓 Heartbeat - Script rodando há {(time.time() - inicio) / 3600:.1f}h")
        ultimo_heartbeat = time.time()

# ===============================================================
# 🔄 FUNÇÃO PARA RECARREGAR VARIÁVEIS DO EPM
# ===============================================================
def recarregar_variaveis_epm():
    """Recarrega as variáveis do EPM e atualiza device_map"""
    logging.info("🔄 Recarregando variáveis do EPM...")
    
    variaveis_ok = 0
    variaveis_nao_encontradas = []
    
    for device_id, info in device_map.items():
        try:
            var_path = info["var_path"]
            
            # Carregar variável
            bv_object = connection.getDataObjects(var_path)
            
            # Validação
            if bv_object and isinstance(bv_object, dict) and var_path in bv_object and bv_object[var_path] is not None:
                # ✅ Variável encontrada
                if info["obj"] is None:
                    logging.info(f"  🆕 Nova variável encontrada: {var_path}")
                info["obj"] = bv_object[var_path]
                variaveis_ok += 1
            else:
                # ❌ Variável não encontrada
                if info["obj"] is not None:
                    logging.warning(f"  ⚠️ Variável perdida: {var_path}")
                info["obj"] = None
                variaveis_nao_encontradas.append(var_path)
                
        except Exception as e:
            if info["obj"] is not None:
                logging.error(f"  ❌ Erro ao recarregar {info['var_path']}: {e}")
            info["obj"] = None
            variaveis_nao_encontradas.append(info["var_path"])
    
    logging.info(f"📊 Recarga concluída: {variaveis_ok}/{len(device_map)} variáveis ativas")
    
    if variaveis_nao_encontradas:
        logging.debug(f"   Variáveis não encontradas: {', '.join(variaveis_nao_encontradas)}")
    
    return variaveis_ok



# ===============================================================
# 🔄 LOOP PRINCIPAL COM RECARGA PERIÓDICA
# ===============================================================
logging.info("🚀 Iniciando sincronização contínua ThingsBoard → EPM...")
logging.info(f"⏱️  Intervalo de polling: {polling} segundos")
logging.info(f"🔑 Chave de telemetria: {chave_telemetria}")
if asset_id:
    logging.info(f"🎯 Filtrando por Asset: {asset_name}")
logging.info("")

inicio = time.time()
contador_sucesso = 0
contador_erro = 0
ciclo = 0
erros_consecutivos = 0

# ✅ CONFIGURAÇÃO DE RECARGA
RECARREGAR_A_CADA_N_CICLOS = config.recarregar_variaveis_a_cada
ultimo_ciclo_recarga = 0

while True:
    try:
        ciclo += 1
        escritas_ciclo = 0
        erros_ciclo = 0
        
        # ✅ RECARREGAR VARIÁVEIS PERIODICAMENTE
        if ciclo - ultimo_ciclo_recarga >= RECARREGAR_A_CADA_N_CICLOS:
            try:
                recarregar_variaveis_epm()
                ultimo_ciclo_recarga = ciclo
            except Exception as e:
                logging.error(f"❌ Erro ao recarregar variáveis: {e}")
        
        # Heartbeat
        log_heartbeat()
        
        # Obter headers com token válido
        headers = obter_headers()
        
        for device_id, info in device_map.items():
            if info["obj"] is None:
                continue
            
            try:
                # Buscar telemetria
                url = f"{TB_URL}/api/plugins/telemetry/DEVICE/{device_id}/values/timeseries?keys={chave_telemetria}"
                response = requests.get(url, headers=headers, verify=False, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Validações
                if not data or chave_telemetria not in data or not data[chave_telemetria]:
                    logging.debug(f"⚠️  {info['name']} - Sem dados")
                    continue
                
                telemetry_data = data[chave_telemetria][0]
                
                if telemetry_data.get('value') is None:
                    logging.warning(f"⚠️  {info['name']} - Valor é None")
                    continue
                
                # Converter e escrever
                valor = float(telemetry_data['value'])
                timestamp_ms = int(telemetry_data['ts'])
                date = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
                quality = 0
                
                info["obj"].write(valor, date, quality)
                
                contador_sucesso += 1
                escritas_ciclo += 1
                erros_consecutivos = 0
                
                logging.info(f"✅ {date.strftime('%Y-%m-%d %H:%M:%S')} | {info['name']} → {info['var_path']} = {valor:.2f}")
                
            except requests.exceptions.RequestException as e:
                erros_ciclo += 1
                logging.warning(f"⚠️ Erro de rede em {info['name']}: {e}")
                
            except Exception as e:
                contador_erro += 1
                erros_ciclo += 1
                logging.error(f"❌ Erro em {info['name']}: {type(e).__name__} - {e}")
        
        # Log do ciclo
        if escritas_ciclo > 0:
            logging.info(f"📊 Ciclo #{ciclo} - Escritas: {escritas_ciclo} | Total: ✅ {contador_sucesso} | ❌ {contador_erro}")
        else:
            logging.debug(f"⏭️  Ciclo #{ciclo} - Sem dados novos")
        
        logging.info("")
        
        # Verificar erros consecutivos
        if erros_ciclo == len([d for d in device_map.values() if d["obj"] is not None]):
            erros_consecutivos += 1
            logging.warning(f"⚠️ Ciclo com 100% de erros ({erros_consecutivos}/{MAX_ERROS_CONSECUTIVOS})")
            
            if erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
                logging.error("❌ Muitos erros consecutivos - Tentando reconectar...")
                try:
                    connection.close()
                    connection = conectar_epm()
                    token, token_timestamp = obter_token_thingsboard()
                    recarregar_variaveis_epm()  # ✅ Recarregar após reconexão
                    erros_consecutivos = 0
                    logging.info("✅ Reconexão bem-sucedida")
                except Exception as e:
                    logging.critical(f"💀 Falha na reconexão: {e}")
                    break
        else:
            erros_consecutivos = 0

    except KeyboardInterrupt:
        logging.info("🛑 Sincronização interrompida pelo usuário")
        break
        
    except Exception as e:
        logging.error(f"❌ Erro crítico no loop: {e}")
        import traceback
        logging.error(traceback.format_exc())
        erros_consecutivos += 1
        
        if erros_consecutivos >= MAX_ERROS_CONSECUTIVOS:
            logging.critical("💀 Erros críticos consecutivos - Encerrando")
            break
    
    time.sleep(polling)

# Cleanup
try:
    connection.close()
except:
    pass

tempo_execucao = (time.time() - inicio) / 3600
logging.info(f"🔌 Conexão fechada após {tempo_execucao:.1f}h de execução")
logging.info(f"📈 Estatísticas finais: ✅ {contador_sucesso} sucessos | ❌ {contador_erro} erros")