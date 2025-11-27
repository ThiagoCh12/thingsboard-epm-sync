import epmwebapi as epm
import json
import ssl
import urllib3

# Desabilitar warnings SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Se necessário, desabilitar verificação SSL
ssl._create_default_https_context = ssl._create_unverified_context
import epmwebapi as epm
import json
import datetime

# Carregar config
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

epm_conf = config["epm"]

print("=" * 70)
print("TESTE DE LEITURA/ESCRITA EPM")
print("=" * 70)

try:
    print("\n1️⃣ Conectando ao EPM Server...")
    connection = epm.EpmConnection(
        epm_conf["url_api"],
        epm_conf["url_auth"],
        epm_conf["user"],
        epm_conf["password"]
    )
    print("✅ Conectado com sucesso!")
    
    print("\n2️⃣ Testando variáveis específicas com leitura/escrita...\n")
    
    test_vars = [
        "STE_Barragem_Med_PZ01"
    ]
    
    for var_name in test_vars:
        try:
            # Tentar obter o objeto da variável
            bv_object = connection.getDataObjects(var_name)
            
            if not bv_object:
                print(f"   ❌ {var_name} - getDataObjects retornou vazio")
                continue
            
            if var_name not in bv_object:
                print(f"   ❌ {var_name} - variável não está no dicionário retornado")
                print(f"      Chaves disponíveis: {list(bv_object.keys())}")
                continue
            
            var_obj = bv_object[var_name]
            
            if var_obj is None:
                print(f"   ❌ {var_name} - objeto é None")
                continue
            
            # Tentar escrever um valor de teste
            test_value = 123.45
            test_date = datetime.datetime.now()
            var_obj.write(test_value, test_date, 0)
            
            print(f"   ✅ {var_name} - EXISTE e ESCRITA OK (valor teste: {test_value})")
            
        except Exception as e:
            print(f"   ❌ {var_name} - ERRO: {type(e).__name__}: {e}")
    
    connection.close()
    print("\n✅ Teste concluído!")
    
except Exception as e:
    print(f"\n❌ ERRO na conexão: {e}")
    import traceback
    traceback.print_exc()

print("=" * 70)