# 📊 Sistema de Sincronização ThingsBoard → EPM

Sistema automatizado para sincronização de telemetrias do ThingsBoard para o EPM Server, com suporte a reconexão automática, renovação de token e monitoramento contínuo.

---

## 📋 Índice

- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Uso](#-uso)
- [Estrutura de Arquivos](#-estrutura-de-arquivos)
- [Monitoramento](#-monitoramento)
- [Solução de Problemas](#-solução-de-problemas)

---

## 🔧 Requisitos

### Software Necessário

- Python 3.7 ou superior
- EPM Studio (para criar variáveis)
- Acesso ao ThingsBoard
- Acesso ao EPM Server

### Bibliotecas Python

```bash
pip install epmwebapi requests python-dotenv urllib3
```

---

## 📦 Instalação

### 1. Clone ou baixe o projeto

```bash
git clone <seu-repositorio>
cd thingsboard-epm-sync
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure o arquivo `.env`

Cole o arquivo `.env` enviado no seu email

---

## ⚙️ Configuração

### 1. Arquivo `.env`

Cole e Edite o arquivo `.env` enviado via email com suas credenciais:

```env
EPM_USER=seu-usuario-epm
EPM_PASSWORD=sua-senha-epm
```

---

## 🚀 Uso

### Iniciar Sincronização

```bash
python sync.py
```

### Executar em Background (Linux)

```bash
nohup python sync.py > output.log 2>&1 &
```

### Executar como Serviço (Linux - systemd)

Crie o arquivo `/etc/systemd/system/tb-epm-sync.service`:

```ini
[Unit]
Description=ThingsBoard to EPM Sync Service
After=network.target

[Service]
Type=simple
User=seu-usuario
WorkingDirectory=/caminho/para/projeto
ExecStart=/usr/bin/python3 /caminho/para/projeto/sync.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Ative e inicie o serviço:

```bash
sudo systemctl enable tb-epm-sync
sudo systemctl start tb-epm-sync
sudo systemctl status tb-epm-sync
```

---

## 📁 Estrutura de Arquivos

```
thingsboard-epm-sync/
│
├── sync.py              # Script principal de sincronização
├── config.py            # Configurações e validações
├── mapping.json         # Mapeamento devices → variáveis EPM
├── .env                 # Credenciais 
├── requirements.txt     # Dependências Python
├── README.md            # Este arquivo
│
└── logs/
    ├── sync.log         # Log principal (rotacionado)
    ├── sync.log.1       # Backup do log anterior
    └── ...              # Até 5 backups
```

---

## 📊 Monitoramento

### Logs

O sistema gera logs detalhados em `sync.log`:

```bash
# Visualizar logs em tempo real
tail -f sync.log

# Ver últimas 100 linhas
tail -n 100 sync.log

# Filtrar apenas erros
grep "ERROR" sync.log
```

### Indicadores no Log

| Emoji | Significado |
|-------|-------------|
| ✅ | Operação bem-sucedida |
| ❌ | Erro |
| ⚠️ | Aviso |
| 🔗 | Conexão |
| 💓 | Heartbeat (status periódico) |
| 🔄 | Recarga/reconexão |
| 📊 | Estatísticas |

### Exemplo de Log

```
2025-01-15 10:30:00 [INFO] 🚀 Iniciando sincronização contínua ThingsBoard → EPM...
2025-01-15 10:30:00 [INFO] ⏱️  Intervalo de polling: 1800 segundos
2025-01-15 10:30:00 [INFO] 🔑 Chave de telemetria: Nível em Cota
2025-01-15 10:30:00 [INFO] 🎯 Filtrando por Asset: Usina Hidrelétrica
2025-01-15 10:30:05 [INFO] ✅ 2025-01-15 10:30:05 | Sensor_Nivel → Usina.Reservatorio.Nivel = 123.45
2025-01-15 10:30:05 [INFO] 📊 Ciclo #1 - Escritas: 15 | Total: ✅ 15 | ❌ 0
2025-01-15 10:35:00 [INFO] 💓 Heartbeat - Script rodando há 0.1h
```

---


